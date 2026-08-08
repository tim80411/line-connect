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

    def _token_usable(self, reply_token: str | None, event_ts_ms: int | None) -> bool:
        if not reply_token or reply_token in self._consumed:
            return False
        if event_ts_ms is None:
            return True
        age_ms = time.time() * 1000 - event_ts_ms
        return age_ms < self._settings.reply_token_ttl_seconds * 1000

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

        if self._token_usable(reply_token, event_ts_ms):
            assert reply_token is not None
            self._consume(reply_token)  # one shot even if it fails — LINE burns it
            if await self._line.reply(reply_token, messages):
                await asyncio.to_thread(self._repo.mark_reply_sent, job_id)
                return True
            log.info("reply_failed_fallback_push", job_id=job_id)

        if await self._line.push(target, messages):
            await asyncio.to_thread(self._repo.mark_reply_sent, job_id)
            return True

        # Last resort (risk R5): LINE validates the whole batch — one bad image
        # URL fails everything. Retry once with text content only.
        text_only = [m for m in messages if m.get("type") == "text"]
        if text_only and len(text_only) < len(messages):
            log.warning("push_failed_retry_text_only", job_id=job_id)
            if await self._line.push(target, text_only):
                await asyncio.to_thread(self._repo.mark_reply_sent, job_id)
                return True

        log.error("delivery_failed", job_id=job_id, target=target[:12])
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
