"""Media debounce: batch rapid-fire uploads into one Dify call (plan §5.4).

Upstream blocked a worker thread with time.sleep(debounce) — the only reason
its cap was 5 seconds. Here the timer is a cancellable asyncio task that costs
nothing while waiting, and the flush is routed back through the owning chat's
shard so ordering guarantees hold.

Buffers are keyed (chat_key, kind) with kind ∈ {image, file} — upstream shared
one key and let a PDF contaminate an image batch.

Buffers live in memory only. A crash mid-debounce loses the batch (the inbox
rows are already 'done'); with seconds-scale windows this is an accepted,
upstream-equivalent loss.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)

BufferKey = tuple[str, str]  # (chat_key, kind)


@dataclass
class MediaBuffer:
    files: list[dict[str, Any]] = field(default_factory=list)
    msg_labels: list[str] = field(default_factory=list)  # LINE message types
    last_job_id: int = 0
    reply_token: str | None = None
    event_ts_ms: int | None = None
    dify_user: str = "unknown"
    # The name the AI is told — admin custom_name wins over the LINE profile.
    effective_name: str | None = None
    target: str = ""
    timer: asyncio.Task[None] | None = None


class MediaDebouncer:
    def __init__(
        self, delay_seconds: float, submit_flush: Callable[[str, str], None]
    ) -> None:
        self._delay = delay_seconds
        self._submit_flush = submit_flush
        self._buffers: dict[BufferKey, MediaBuffer] = {}

    @property
    def enabled(self) -> bool:
        return self._delay > 0

    def add(
        self,
        chat_key: str,
        kind: str,
        *,
        file_obj: dict[str, Any],
        msg_label: str,
        job_id: int,
        reply_token: str | None,
        event_ts_ms: int | None,
        dify_user: str,
        effective_name: str | None,
        target: str,
    ) -> int:
        """Buffer one uploaded file and (re)arm the timer. Returns batch size.

        Only ever called from the chat's shard worker — single event loop, one
        writer per buffer, no lock needed.
        """
        buf = self._buffers.setdefault((chat_key, kind), MediaBuffer())
        buf.files.append(file_obj)
        buf.msg_labels.append(msg_label)
        buf.last_job_id = job_id
        # Newest token: most likely still valid when the batch flushes.
        buf.reply_token = reply_token
        buf.event_ts_ms = event_ts_ms
        buf.dify_user = dify_user
        buf.effective_name = effective_name
        buf.target = target
        if buf.timer is not None:
            buf.timer.cancel()
        buf.timer = asyncio.create_task(self._fire_after(chat_key, kind))
        return len(buf.files)

    async def _fire_after(self, chat_key: str, kind: str) -> None:
        await asyncio.sleep(self._delay)
        # Route through the shard queue: the flush runs on the chat's worker,
        # serialized with any messages that arrived meanwhile.
        self._submit_flush(chat_key, kind)

    def pop(self, chat_key: str, kind: str) -> MediaBuffer | None:
        buf = self._buffers.pop((chat_key, kind), None)
        if buf is not None and buf.timer is not None:
            buf.timer.cancel()
            buf.timer = None
        return buf

    def cancel_all(self) -> None:
        for buf in self._buffers.values():
            if buf.timer is not None:
                buf.timer.cancel()
        if self._buffers:
            log.warning("debounce_buffers_dropped", count=len(self._buffers))
        self._buffers.clear()
