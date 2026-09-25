"""Reply-token-first delivery with push fallback (plan §5.5).

Two improvements over upstream's reply-then-push:
(a) tokens past their usable window skip the doomed reply call — background
    processing means tokens are often expired by send time. The window is
    LINE's, modelled in line.reply_token: it runs from when the delivery
    reached us, so a redelivered event still gets a free reply;
(b) used/burned tokens are remembered so a debounced batch never reuses one.

Reply stays preferred because LINE bills Push messages against the plan quota;
Reply is free. Once LINE reports that quota spent, push is skipped for a
cooldown (every attempt would be refused), and an answer that reaches the
user by neither path is recorded on its job as 'delivery_failed'.
"""

import asyncio
import time
from typing import Any

import structlog

from line_connect.config import Settings
from line_connect.line.client import LineClient, SendResult
from line_connect.line.messages import LINE_MAX_MESSAGES, text_msg
from line_connect.line.reply_token import ReplyToken
from line_connect.storage.repository import InboxJob, Repository

log = structlog.get_logger(__name__)

CONSUMED_TOKENS_MAX = 1024


def reply_token_of(job: InboxJob) -> ReplyToken:
    return ReplyToken(
        value=job.reply_token, received_ms=job.received_ms, event_ts_ms=job.event_ts_ms
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


class Replier:
    def __init__(self, settings: Settings, line: LineClient, repo: Repository) -> None:
        self._settings = settings
        self._line = line
        self._repo = repo
        self._consumed: dict[str, None] = {}  # insertion-ordered set
        self._push_blocked_until = 0.0  # monotonic; quota-exhausted breaker

    def _consume(self, token: str) -> None:
        self._consumed[token] = None
        while len(self._consumed) > CONSUMED_TOKENS_MAX:
            self._consumed.pop(next(iter(self._consumed)))

    def _reply_skip_reason(self, token: ReplyToken) -> str | None:
        """None when the token is worth a reply attempt, else why not."""
        if token.value and token.value in self._consumed:
            return "token_consumed"
        return token.skip_reason(
            _now_ms(), int(self._settings.reply_token_ttl_seconds * 1000)
        )

    def _push_blocked(self) -> bool:
        return time.monotonic() < self._push_blocked_until

    def _block_push(self) -> None:
        cooldown = self._settings.push_quota_cooldown_seconds
        self._push_blocked_until = time.monotonic() + cooldown
        log.error("push_quota_exhausted", cooldown_seconds=cooldown)

    async def _delivered(
        self, job_id: int, via: str, skip_reason: str | None, token: ReplyToken
    ) -> bool:
        await asyncio.to_thread(self._repo.mark_reply_sent, job_id)
        # One line per delivered job: `via` gives the reply hit rate directly;
        # reply_skip says why a push was needed without re-deriving it.
        log.info(
            "delivered",
            job_id=job_id,
            via=via,
            reply_skip=skip_reason,
            token_age_ms=token.age_ms(_now_ms()),
        )
        return True

    async def send(
        self,
        job_id: int,
        target: str,
        token: ReplyToken,
        messages: list[dict[str, Any]],
    ) -> bool:
        messages = messages[:LINE_MAX_MESSAGES]
        if not messages:
            return False

        skip_reason = self._reply_skip_reason(token)
        if skip_reason is None:
            assert token.value is not None
            self._consume(token.value)  # one shot even if it fails — LINE burns it
            if (await self._line.reply(token.value, messages)).ok:
                return await self._delivered(job_id, "reply", None, token)
            log.info("reply_failed_fallback_push", job_id=job_id)
            skip_reason = "reply_rejected"

        if self._push_blocked():
            reason = "push_quota_exhausted"  # LINE would refuse again; don't ask
        else:
            result = await self._push(job_id, target, messages)
            if result.ok:
                return await self._delivered(job_id, "push", skip_reason, token)
            reason = (
                "push_quota_exhausted"
                if result.quota_exhausted
                else f"push_failed:{result.status or 'transport'}"
            )
        log.error(
            "delivery_failed",
            job_id=job_id,
            target=target[:12],
            reply_skip=skip_reason,
            reason=reason,
        )
        await asyncio.to_thread(self._repo.mark_delivery_failed, job_id, reason)
        return False

    async def _push(
        self, job_id: int, target: str, messages: list[dict[str, Any]]
    ) -> SendResult:
        result = await self._line.push(target, messages)

        # Last resort (risk R5): LINE validates the whole batch — one bad image
        # URL fails everything. Retry once with text content only. Not on a
        # 429: a quota or rate refusal would refuse the smaller batch too.
        text_only = [m for m in messages if m.get("type") == "text"]
        if not result.ok and result.status != 429 and 0 < len(text_only) < len(messages):
            log.warning("push_failed_retry_text_only", job_id=job_id)
            result = await self._line.push(target, text_only)

        if result.quota_exhausted:
            self._block_push()
        return result

    async def send_text(
        self,
        job_id: int,
        target: str,
        token: ReplyToken,
        text: str,
    ) -> bool:
        return await self.send(job_id, target, token, [text_msg(text)])
