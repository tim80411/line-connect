"""Reply-token-first delivery with push fallback (plan §5.5).

Two improvements over upstream's reply-then-push:
(a) tokens older than REPLY_TOKEN_TTL_SECONDS skip the doomed reply call —
    background processing means tokens are often expired by send time;
(b) used/burned tokens are remembered so a debounced batch never reuses one.

Reply stays preferred because LINE bills Push messages against the plan quota;
Reply is free.
"""

import asyncio
import time
from typing import Any

import structlog

from line_connect.config import Settings
from line_connect.line.client import LineClient
from line_connect.line.messages import LINE_MAX_MESSAGES, text_msg
from line_connect.storage.repository import Repository

log = structlog.get_logger(__name__)

CONSUMED_TOKENS_MAX = 1024


class Replier:
    def __init__(self, settings: Settings, line: LineClient, repo: Repository) -> None:
        self._settings = settings
        self._line = line
        self._repo = repo
        self._consumed: dict[str, None] = {}  # insertion-ordered set

    def _consume(self, token: str) -> None:
        self._consumed[token] = None
        while len(self._consumed) > CONSUMED_TOKENS_MAX:
            self._consumed.pop(next(iter(self._consumed)))

    def _reply_skip_reason(
        self, reply_token: str | None, event_ts_ms: int | None
    ) -> str | None:
        """None when the token is worth a reply attempt, else why not."""
        if not reply_token:
            return "no_token"
        if reply_token in self._consumed:
            return "token_consumed"
        if event_ts_ms is None:
            return None
        age_ms = time.time() * 1000 - event_ts_ms
        if age_ms >= self._settings.reply_token_ttl_seconds * 1000:
            return "token_expired"
        return None

    async def _delivered(
        self, job_id: int, via: str, skip_reason: str | None, event_ts_ms: int | None
    ) -> bool:
        await asyncio.to_thread(self._repo.mark_reply_sent, job_id)
        # One line per delivered job: `via` gives the reply hit rate directly;
        # reply_skip says why a push was needed without re-deriving it.
        log.info(
            "delivered",
            job_id=job_id,
            via=via,
            reply_skip=skip_reason,
            token_age_ms=(
                int(time.time() * 1000) - event_ts_ms if event_ts_ms is not None else None
            ),
        )
        return True

    async def send(
        self,
        job_id: int,
        target: str,
        reply_token: str | None,
        event_ts_ms: int | None,
        messages: list[dict[str, Any]],
    ) -> bool:
        messages = messages[:LINE_MAX_MESSAGES]
        if not messages:
            return False

        skip_reason = self._reply_skip_reason(reply_token, event_ts_ms)
        if skip_reason is None:
            assert reply_token is not None
            self._consume(reply_token)  # one shot even if it fails — LINE burns it
            if await self._line.reply(reply_token, messages):
                return await self._delivered(job_id, "reply", None, event_ts_ms)
            log.info("reply_failed_fallback_push", job_id=job_id)
            skip_reason = "reply_rejected"

        if await self._line.push(target, messages):
            return await self._delivered(job_id, "push", skip_reason, event_ts_ms)

        # Last resort (risk R5): LINE validates the whole batch — one bad image
        # URL fails everything. Retry once with text content only.
        text_only = [m for m in messages if m.get("type") == "text"]
        if text_only and len(text_only) < len(messages):
            log.warning("push_failed_retry_text_only", job_id=job_id)
            if await self._line.push(target, text_only):
                return await self._delivered(job_id, "push", skip_reason, event_ts_ms)

        log.error("delivery_failed", job_id=job_id, target=target[:12], reply_skip=skip_reason)
        return False

    async def send_text(
        self,
        job_id: int,
        target: str,
        reply_token: str | None,
        event_ts_ms: int | None,
        text: str,
    ) -> bool:
        return await self.send(job_id, target, reply_token, event_ts_ms, [text_msg(text)])
