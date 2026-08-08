"""Event handlers — the bridge between a claimed inbox job and Dify.

Runs inside a pipeline worker: same chat_key → same worker → strictly serial,
so conversation state reads/writes here need no locking.
"""

import asyncio
import contextlib
import mimetypes
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from line_connect.config import Settings
from line_connect.dify.client import DifyClient
from line_connect.formatting import build_reply
from line_connect.line.client import LineClient
from line_connect.line.events import LineEvent, LineMessage, LineSource
from line_connect.line.messages import push_target
from line_connect.pipeline.debounce import MediaDebouncer
from line_connect.pipeline.notify import Notifier
from line_connect.pipeline.replier import Replier
from line_connect.storage.repository import InboxJob, Repository

if TYPE_CHECKING:
    from line_connect.admin.media_store import MediaStore
    from line_connect.pipeline.queue import Pipeline

log = structlog.get_logger(__name__)

EMPTY_ANSWER_MESSAGE = "Sorry, I couldn't generate a response."
MEDIA_UNSUPPORTED_MESSAGE = "Sorry, image messages are not supported."
EMPTY_MEDIA_ANSWERS = {"image": "Image received.", "file": "File received."}
LOADING_REARM_INTERVAL_SECONDS = 50.0


def media_meta(message: LineMessage, content_type: str) -> tuple[str, str, str]:
    """(filename, mimetype, dify_file_type) for a LINE media message."""
    if message.type == "image":
        return f"{message.id}.jpg", "image/jpeg", "image"
    if message.type == "video":
        return f"{message.id}.mp4", "video/mp4", "video"
    if message.type == "audio":
        return f"{message.id}.m4a", "audio/mp4", "audio"
    if message.file_name:
        guessed = mimetypes.guess_type(message.file_name)[0]
        return (
            message.file_name,
            guessed or content_type or "application/octet-stream",
            "document",
        )
    return f"{message.id}.bin", content_type or "application/octet-stream", "document"


def build_inputs(display_name: str | None, settings: Settings) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    if settings.pass_display_name:
        inputs[settings.display_name_variable] = display_name or "LINE User"
    return inputs


@dataclass(frozen=True)
class Identity:
    """Who this message is from, in the three forms the pipeline needs.

    `effective_name` is what the AI is told (admin's custom_name wins).
    `display_name` is the real LINE name — logged as-is so the dashboard can
    show the original alongside the override.
    `dify_user` is deliberately NOT affected by custom_name: it keys the Dify
    end-user identity, so renaming a chat in the dashboard would otherwise fork
    that user's history. Upstream has this bug (endpoints/line.py:327-329).
    """

    effective_name: str | None
    display_name: str | None
    picture_url: str | None
    dify_user: str


def source_id_of(source: LineSource) -> str:
    return source.group_id or source.room_id or source.user_id or "unknown"


class Bridge:
    def __init__(
        self,
        settings: Settings,
        repo: Repository,
        line: LineClient,
        dify: DifyClient,
        replier: Replier,
        notifier: Notifier,
        media: "MediaStore | None" = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._line = line
        self._dify = dify
        self._replier = replier
        self._notifier = notifier
        self._media = media
        self._debouncer: MediaDebouncer | None = None

    def attach_pipeline(self, pipeline: "Pipeline") -> None:
        """Late binding: the debounce timer routes flushes back through the
        pipeline's shard queues, and the pipeline calls back into this bridge."""
        delay = min(
            self._settings.media_debounce_seconds,
            self._settings.media_debounce_max_seconds,
        )
        self._debouncer = MediaDebouncer(delay, pipeline.submit_flush)

    def cancel_debounce(self) -> None:
        if self._debouncer is not None:
            self._debouncer.cancel_all()

    # ── pipeline entry points ──────────────────────────────────────

    async def handle_event(self, job: InboxJob) -> None:
        event = LineEvent.from_json(job.event_json)
        if event.type == "follow":
            await self.handle_follow(job, event)
        elif event.type == "message" and event.message is not None:
            if event.message.type == "text":
                await self.handle_text(job, event)
            elif event.message.type in ("image", "video", "audio", "file"):
                await self.handle_media(job, event)
            # stickers, locations, etc.: ignore silently (upstream behavior)

    async def on_job_failure(self, job: InboxJob, exc: BaseException) -> None:
        await self._notifier.notify_job_failure(job, exc)

    # ── follow ─────────────────────────────────────────────────────

    async def handle_follow(self, job: InboxJob, event: LineEvent) -> None:
        target = push_target(event.source)
        if not target:
            return
        await self._replier.send_text(
            job.id, target, event.reply_token, event.timestamp,
            self._settings.welcome_message,
        )

    # ── text ───────────────────────────────────────────────────────

    async def handle_text(self, job: InboxJob, event: LineEvent) -> None:
        assert event.message is not None
        text = event.message.text or ""
        chat_key = job.chat_key
        source = event.source
        target = push_target(source)

        if text.strip().lower() in self._settings.clear_command_list:
            # Only the Dify conversation id is dropped, not the row: the chat's
            # admin meta (custom_name / notes / tags / starred) has to survive a
            # user typing /clear. Same semantics as upstream, which only deleted
            # its cid key.
            await asyncio.to_thread(self._repo.clear_cid, chat_key)
            await self._replier.send_text(
                job.id, target, event.reply_token, event.timestamp,
                self._settings.clear_confirm_message,
            )
            log.info("conversation_cleared", chat_key=chat_key)
            return

        async with self._loading_indicator(source):
            who = await self._resolve_identity(source, chat_key)
            await asyncio.to_thread(
                self._repo.ensure_conversation,
                chat_key, source.type, source_id_of(source),
                who.dify_user, who.display_name, who.picture_url,
            )
            if self._settings.message_log_enabled:
                await asyncio.to_thread(
                    self._repo.log_message,
                    chat_key, "user", text,
                    "text", event.message.id, None, who.display_name, None,
                )

            cid = await asyncio.to_thread(self._repo.get_cid, chat_key)
            result, latency_ms = await self._chat_with_cid_protection(
                chat_key,
                query=text,
                dify_user=who.dify_user,
                inputs=build_inputs(who.effective_name, self._settings),
                cid=cid,
            )

            if not result.answer:
                await self._replier.send_text(
                    job.id, target, event.reply_token, event.timestamp, EMPTY_ANSWER_MESSAGE
                )
                return

            if self._settings.message_log_enabled:
                await asyncio.to_thread(
                    self._repo.log_message,
                    chat_key, "bot", result.answer,
                    "text", None, result.conversation_id, None, latency_ms,
                )
            messages = build_reply(
                result.answer,
                flex_enabled=self._settings.flex_message_enabled,
                strip_md=self._settings.strip_markdown,
            )
            await self._replier.send(
                job.id, target, event.reply_token, event.timestamp, messages
            )

    # ── media ──────────────────────────────────────────────────────

    async def handle_media(self, job: InboxJob, event: LineEvent) -> None:
        assert event.message is not None
        message = event.message
        if not self._settings.media_support_enabled:
            # Upstream: images get an explicit "unsupported" reply, other
            # media types are ignored silently.
            if message.type == "image":
                await self._replier.send_text(
                    job.id,
                    push_target(event.source),
                    event.reply_token,
                    event.timestamp,
                    MEDIA_UNSUPPORTED_MESSAGE,
                )
            return

        source = event.source
        chat_key = job.chat_key
        target = push_target(source)
        kind = "image" if message.type == "image" else "file"

        async with self._loading_indicator(source):
            who = await self._resolve_identity(source, chat_key)
            await asyncio.to_thread(
                self._repo.ensure_conversation,
                chat_key, source.type, source_id_of(source),
                who.dify_user, who.display_name, who.picture_url,
            )

            try:
                data, content_type = await self._line.download_content(
                    message.id, self._settings.media_max_download_bytes
                )
            except Exception as exc:
                log.warning(
                    "media_download_failed", chat_key=chat_key, error=str(exc)[:200]
                )
                if self._settings.debug_mode:
                    await self._replier.send_text(
                        job.id, target, event.reply_token, event.timestamp,
                        f"[DEBUG] Download failed: {str(exc)[:300]}",
                    )
                return

            if self._media is not None:
                # Store what we already have in memory, before Dify sees it —
                # a failed upload should not cost the operator the image.
                await self._media.save(chat_key, message.id, data, content_type)

            filename, mimetype, dify_type = media_meta(message, content_type)
            file_info = await self._dify.upload_file(
                filename, data, mimetype, who.dify_user
            )
            if file_info is None:
                if self._settings.debug_mode:
                    await self._replier.send_text(
                        job.id, target, event.reply_token, event.timestamp,
                        "[DEBUG] Upload to Dify failed",
                    )
                return
            file_obj = {
                "type": dify_type,
                "transfer_method": "local_file",
                "upload_file_id": file_info["id"],
            }

            if self._settings.message_log_enabled:
                await asyncio.to_thread(
                    self._repo.log_message,
                    chat_key, "user", f"[{message.type}]",
                    message.type, message.id, None, who.display_name, None,
                )

            assert self._debouncer is not None, "attach_pipeline() not called"
            if self._debouncer.enabled:
                count = self._debouncer.add(
                    chat_key,
                    kind,
                    file_obj=file_obj,
                    msg_label=message.type,
                    job_id=job.id,
                    reply_token=event.reply_token,
                    event_ts_ms=event.timestamp,
                    dify_user=who.dify_user,
                    effective_name=who.effective_name,
                    target=target,
                )
                log.info("media_buffered", chat_key=chat_key, kind=kind, count=count)
                return

            await self._flush_files(
                chat_key,
                kind,
                files=[file_obj],
                msg_labels=[message.type],
                job_id=job.id,
                reply_token=event.reply_token,
                event_ts_ms=event.timestamp,
                dify_user=who.dify_user,
                effective_name=who.effective_name,
                target=target,
            )

    async def flush_media(self, chat_key: str, kind: str) -> None:
        """Called by the pipeline on the chat's own shard when a debounce
        window closes."""
        assert self._debouncer is not None
        buf = self._debouncer.pop(chat_key, kind)
        if buf is None or not buf.files:
            return
        await self._flush_files(
            chat_key,
            kind,
            files=buf.files,
            msg_labels=buf.msg_labels,
            job_id=buf.last_job_id,
            reply_token=buf.reply_token,
            event_ts_ms=buf.event_ts_ms,
            dify_user=buf.dify_user,
            effective_name=buf.effective_name,
            target=buf.target,
        )

    async def _flush_files(
        self,
        chat_key: str,
        kind: str,
        *,
        files: list[dict[str, Any]],
        msg_labels: list[str],
        job_id: int,
        reply_token: str | None,
        event_ts_ms: int | None,
        dify_user: str,
        effective_name: str | None,
        target: str,
    ) -> None:
        inputs = build_inputs(effective_name, self._settings)
        if kind == "image":
            inputs[self._settings.dify_image_variable] = files
            # User's IMAGE_PROMPT wins for a single image; the multi template
            # applies only to batches (upstream overwrote it with hardcoded Thai).
            if len(files) > 1:
                query = self._settings.multi_image_prompt_template.format(count=len(files))
            else:
                query = self._settings.image_prompt
        else:
            inputs[self._settings.dify_file_variable] = files
            query = self._settings.file_prompt_template.format(
                kind=msg_labels[-1] if msg_labels else "file"
            )

        cid = await asyncio.to_thread(self._repo.get_cid, chat_key)
        result, latency_ms = await self._chat_with_cid_protection(
            chat_key, query=query, dify_user=dify_user, inputs=inputs, cid=cid
        )
        answer = result.answer or EMPTY_MEDIA_ANSWERS[kind]

        if self._settings.message_log_enabled:
            await asyncio.to_thread(
                self._repo.log_message,
                chat_key, "bot", answer,
                kind, None, result.conversation_id, None, latency_ms,
            )
        messages = build_reply(
            answer,
            flex_enabled=self._settings.flex_message_enabled,
            strip_md=self._settings.strip_markdown,
        )
        await self._replier.send(job_id, target, reply_token, event_ts_ms, messages)

    # ── shared plumbing ────────────────────────────────────────────

    async def _resolve_identity(self, source: LineSource, chat_key: str) -> Identity:
        display_name, picture_url = (
            await self._line.get_profile(source)
            if self._settings.pass_display_name
            else (None, None)
        )
        custom_name = await asyncio.to_thread(self._repo.get_custom_name, chat_key)
        return Identity(
            effective_name=custom_name or display_name,
            display_name=display_name,
            picture_url=picture_url,
            dify_user=display_name or source.user_id or "unknown",
        )

    async def _chat_with_cid_protection(
        self,
        chat_key: str,
        *,
        query: str,
        dify_user: str,
        inputs: dict[str, Any],
        cid: str | None,
    ) -> tuple[Any, int]:
        """Dify call with the issue-#1 protections: persist the cid on first
        sight (mid-stream), clear it only on explicit conversation-invalid."""

        async def on_cid(new_cid: str) -> None:
            await asyncio.to_thread(self._repo.set_cid, chat_key, new_cid)

        async def on_invalid() -> None:
            log.warning("cid_invalidated", chat_key=chat_key)
            await asyncio.to_thread(self._repo.clear_cid, chat_key)

        t0 = time.monotonic()
        result = await self._dify.chat(
            query,
            dify_user,
            inputs=inputs,
            conversation_id=cid,
            on_conversation_id=on_cid,
            on_conversation_invalid=on_invalid,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        if result.conversation_id and result.conversation_id != cid:
            # Redundant with on_cid for the common path; covers blocking-mode
            # responses and keeps the final word authoritative.
            await asyncio.to_thread(self._repo.set_cid, chat_key, result.conversation_id)
        log.info(
            "dify_answered",
            chat_key=chat_key,
            latency_ms=latency_ms,
            answer_len=len(result.answer),
            cid_prefix=(result.conversation_id or "")[:8],
        )
        return result, latency_ms

    @asynccontextmanager
    async def _loading_indicator(self, source: LineSource) -> AsyncIterator[None]:
        """Typing indicator, re-armed until the job finishes (§5.8). 1:1 chats
        only — the loading API rejects group/room ids."""

        async def rearm_loop(user_id: str) -> None:
            while True:
                await self._line.show_loading(user_id, seconds=60)
                await asyncio.sleep(LOADING_REARM_INTERVAL_SECONDS)

        task: asyncio.Task[None] | None = None
        if source.type == "user" and source.user_id:
            task = asyncio.create_task(rearm_loop(source.user_id))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
