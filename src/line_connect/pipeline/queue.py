"""Sharded in-process job queue backed by the SQLite inbox.

Why shards instead of one queue + a lock: crc32(chat_key) % N pins every chat
to one worker, so messages within a chat are strictly FIFO with no locking.
Two concurrent messages from the same user would otherwise both read an empty
conversation_id and fork two Dify conversations — one of upstream issue #1's
faces. crc32 (not hash()) because hash() of str changes per process with
PYTHONHASHSEED, which would make tests unreproducible.

Durability: the queue holds only inbox row ids. The DB row is the job; a
crash loses nothing but in-flight work, which startup recovery re-enqueues.
"""

import asyncio
import json
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from line_connect.config import Settings
from line_connect.line.events import LineEvent
from line_connect.line.messages import chat_key_of
from line_connect.storage.repository import InboxJob, Repository

log = structlog.get_logger(__name__)

Handler = Callable[[InboxJob], Awaitable[None]]
FailureHook = Callable[[InboxJob, BaseException], Awaitable[None]]
FlushHandler = Callable[[str, str], Awaitable[None]]

HANDLED_EVENT_TYPES = ("message", "follow")


@dataclass(frozen=True)
class FlushMedia:
    """Queue item: flush the (chat_key, kind) debounce buffer on its shard."""

    chat_key: str
    kind: str


QueueItem = int | FlushMedia | None
# None on a worker queue = drain sentinel: finish current job, then exit.


async def _noop_handler(job: InboxJob) -> None:
    log.info("noop_handler", job_id=job.id, chat_key=job.chat_key)


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        repo: Repository,
        handler: Handler | None = None,
        on_failure: FailureHook | None = None,
        flush_handler: FlushHandler | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._handler: Handler = handler or _noop_handler
        self._on_failure = on_failure
        self._flush_handler = flush_handler
        self._queues: list[asyncio.Queue[QueueItem]] = []
        self._workers: list[asyncio.Task[None]] = []
        self._housekeeping: asyncio.Task[None] | None = None
        self._inflight: set[int] = set()
        self._draining = False

    # ── lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        n = self._settings.worker_count
        self._queues = [
            asyncio.Queue(maxsize=self._settings.queue_max_size) for _ in range(n)
        ]
        self._workers = [
            asyncio.create_task(self._worker_loop(i), name=f"worker-{i}") for i in range(n)
        ]
        self._housekeeping = asyncio.create_task(self._housekeeping_loop(), name="housekeeping")

        recovered = await asyncio.to_thread(
            self._repo.recover_orphans, self._settings.max_recovery_age_seconds
        )
        for job in recovered:
            self._enqueue(job.id, job.chat_key)

    async def stop(self) -> None:
        """Graceful drain: finish in-flight jobs within the grace window; anything
        unfinished stays in the DB ('pending'/'processing') for next-boot recovery."""
        self._draining = True
        if self._housekeeping is not None:
            self._housekeeping.cancel()
        for q in self._queues:
            q.put_nowait(None)
        done, pending = await asyncio.wait(
            self._workers, timeout=self._settings.shutdown_grace_seconds
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
            log.warning("shutdown_grace_exceeded", cancelled_workers=len(pending))
        log.info("pipeline_stopped", finished_workers=len(done))

    async def idle(self) -> None:
        """Test helper: resolve once every queued job has been fully processed."""
        await asyncio.gather(*(q.join() for q in self._queues))

    # ── intake ─────────────────────────────────────────────────────

    async def submit_raw(self, raw_event: dict[str, Any]) -> int | None:
        """Persist one webhook event and hand it to a worker.

        Returns the inbox row id, or None when skipped (unhandled type or dup).
        Never raises on malformed events — the webhook must still return 200
        for the rest of the batch.
        """
        try:
            event = LineEvent.model_validate(raw_event)
        except ValueError:
            log.warning("event_parse_failed", raw_keys=sorted(raw_event))
            return None
        if event.type not in HANDLED_EVENT_TYPES:
            return None

        chat_key = chat_key_of(event.source)
        dedup_key = event.dedup_key(chat_key)
        row_id = await asyncio.to_thread(
            self._repo.try_claim_event,
            dedup_key,
            chat_key,
            event.type,
            event.message.type if event.message else None,
            json.dumps(raw_event, ensure_ascii=False),
            event.reply_token,
            event.timestamp,
        )
        if row_id is None:
            log.info(
                "duplicate_event",
                dedup_key=dedup_key,
                chat_key=chat_key,
                redelivery=event.delivery_context.is_redelivery,
            )
            return None
        self._enqueue(row_id, chat_key)
        return row_id

    def shard_of(self, chat_key: str) -> int:
        return zlib.crc32(chat_key.encode("utf-8")) % len(self._queues)

    def _enqueue(self, row_id: int, chat_key: str) -> None:
        if self._draining:
            return  # row stays 'pending' in DB; recovered on next boot
        try:
            self._queues[self.shard_of(chat_key)].put_nowait(row_id)
            self._inflight.add(row_id)
        except asyncio.QueueFull:
            # Row stays 'pending' in DB; the housekeeping sweep will retry.
            log.warning("queue_full", chat_key=chat_key, row_id=row_id)

    def submit_flush(self, chat_key: str, kind: str) -> None:
        """Route a debounce flush to the chat's shard (keeps per-chat FIFO)."""
        if self._draining:
            return
        try:
            self._queues[self.shard_of(chat_key)].put_nowait(FlushMedia(chat_key, kind))
        except asyncio.QueueFull:
            log.warning("queue_full_flush_dropped", chat_key=chat_key, kind=kind)

    def queue_depths(self) -> list[int]:
        return [q.qsize() for q in self._queues]

    # ── workers ────────────────────────────────────────────────────

    async def _worker_loop(self, idx: int) -> None:
        q = self._queues[idx]
        while True:
            item = await q.get()
            if item is None:
                q.task_done()
                return
            if isinstance(item, FlushMedia):
                try:
                    if self._flush_handler is not None:
                        await self._flush_handler(item.chat_key, item.kind)
                except Exception:
                    log.exception("flush_crashed", chat_key=item.chat_key, kind=item.kind)
                finally:
                    q.task_done()
                continue
            try:
                await self._process(item)
            except Exception:
                log.exception("worker_process_crashed", row_id=item)
            finally:
                self._inflight.discard(item)
                q.task_done()

    async def _process(self, row_id: int) -> None:
        job = await asyncio.to_thread(self._repo.get_job, row_id)
        if job is None:
            return
        # Bind the job identity into every log line emitted while handling it —
        # this is what makes a single message traceable end to end.
        structlog.contextvars.bind_contextvars(
            job_id=row_id, chat_key=job.chat_key, dedup_key=job.dedup_key
        )
        try:
            await asyncio.to_thread(self._repo.mark_processing, row_id)
            try:
                async with asyncio.timeout(self._settings.job_timeout_seconds):
                    await self._handler(job)
            except (Exception, asyncio.CancelledError) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    # Shutdown cancellation: leave status 'processing' for recovery.
                    raise
                await asyncio.to_thread(self._repo.mark_failed, row_id, repr(exc))
                log.warning("job_failed", error=repr(exc))
                if self._on_failure is not None:
                    try:
                        await self._on_failure(job, exc)
                    except Exception:
                        log.exception("failure_hook_crashed")
            else:
                await asyncio.to_thread(self._repo.mark_done, row_id)
        finally:
            structlog.contextvars.clear_contextvars()

    # ── housekeeping: retention purge + stranded-pending sweep ─────

    async def _housekeeping_loop(self) -> None:
        interval = 60.0
        purge_every = 3600.0
        elapsed_since_purge = purge_every  # purge on first tick
        while True:
            await asyncio.sleep(interval)
            elapsed_since_purge += interval
            depths = self.queue_depths()
            if any(depths):
                log.info("queue_depth", depths=depths, total=sum(depths))
            try:
                await self._sweep_stranded()
                if elapsed_since_purge >= purge_every:
                    elapsed_since_purge = 0.0
                    purged = await asyncio.to_thread(
                        self._repo.purge_expired,
                        self._settings.dedup_retention_days,
                        self._settings.message_log_retention_days,
                    )
                    if any(purged):
                        log.info("retention_purged", inbox=purged[0], messages=purged[1])
            except Exception:
                log.exception("housekeeping_failed")

    async def _sweep_stranded(self) -> None:
        """Re-enqueue 'pending' rows that fell out of the in-memory queue
        (queue-full at intake). Skips ids currently queued or running."""
        for row_id, chat_key in await asyncio.to_thread(self._repo.list_pending):
            if row_id not in self._inflight:
                self._enqueue(row_id, chat_key)
