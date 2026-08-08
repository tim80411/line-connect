"""Error notifications to the end user, rate-limited per chat.

Without dedup, five queued messages failing against a down Dify would send the
user five identical apologies.
"""

import time
import traceback

import structlog

from line_connect.config import Settings
from line_connect.line.events import LineEvent
from line_connect.line.messages import push_target
from line_connect.pipeline.replier import Replier
from line_connect.storage.repository import InboxJob

log = structlog.get_logger(__name__)

NOTIFY_DEDUP_WINDOW_SECONDS = 60.0
DEBUG_TRACEBACK_LIMIT = 800


class Notifier:
    def __init__(self, settings: Settings, replier: Replier) -> None:
        self._settings = settings
        self._replier = replier
        self._last_notified: dict[str, float] = {}

    def _should_notify(self, chat_key: str) -> bool:
        now = time.monotonic()
        last = self._last_notified.get(chat_key)
        if last is not None and now - last < NOTIFY_DEDUP_WINDOW_SECONDS:
            return False
        self._last_notified[chat_key] = now
        if len(self._last_notified) > 512:
            cutoff = now - NOTIFY_DEDUP_WINDOW_SECONDS
            self._last_notified = {
                k: v for k, v in self._last_notified.items() if v > cutoff
            }
        return True

    def _message_for(self, exc: BaseException) -> str:
        if isinstance(exc, TimeoutError):
            return "Sorry, that took too long to process. Please try again."
        return self._settings.generic_error_message

    async def notify_job_failure(self, job: InboxJob, exc: BaseException) -> None:
        if not self._should_notify(job.chat_key):
            log.info("notify_suppressed", chat_key=job.chat_key)
            return
        text = self._message_for(exc)
        if self._settings.debug_mode:
            tb = "".join(traceback.format_exception(exc))[-DEBUG_TRACEBACK_LIMIT:]
            text = f"[DEBUG] {tb}"
        try:
            event = LineEvent.from_json(job.event_json)
            target = push_target(event.source)
            if not target:
                return
            await self._replier.send_text(
                job.id, target, job.reply_token, job.event_ts_ms, text
            )
        except Exception:
            # Notification is best-effort; never let it cascade.
            log.exception("notify_failed", chat_key=job.chat_key)
