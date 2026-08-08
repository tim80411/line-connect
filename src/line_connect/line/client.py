"""Async LINE Messaging API client (httpx), replacing upstream's sync requests.

Profile lookups get a TTL cache: upstream hit the profile API once per message,
a fixed latency tax on every reply.
"""

import time
from typing import Any

import httpx
import structlog

from line_connect.config import Settings
from line_connect.line.events import LineSource

log = structlog.get_logger(__name__)

LINE_API_BASE = "https://api.line.me/v2"
LINE_DATA_API_BASE = "https://api-data.line.me/v2"

PROFILE_CACHE_TTL_SECONDS = 900.0
PROFILE_CACHE_MAX_ENTRIES = 2048


class LineClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client
        self._headers = {
            "Authorization": f"Bearer {settings.line_channel_access_token}",
            "Content-Type": "application/json",
        }
        self._profile_cache: dict[str, tuple[str | None, float]] = {}

    # ── messaging ──────────────────────────────────────────────────

    async def reply(self, reply_token: str, messages: list[dict[str, Any]]) -> bool:
        try:
            resp = await self._client.post(
                f"{LINE_API_BASE}/bot/message/reply",
                headers=self._headers,
                json={"replyToken": reply_token, "messages": messages},
                timeout=self._settings.line_api_timeout,
            )
        except httpx.TransportError as exc:
            log.warning("line_reply_transport_error", error=str(exc))
            return False
        if resp.status_code == 200:
            return True
        log.warning("line_reply_failed", status=resp.status_code, body=resp.text[:200])
        return False

    async def push(self, to: str, messages: list[dict[str, Any]]) -> bool:
        try:
            resp = await self._client.post(
                f"{LINE_API_BASE}/bot/message/push",
                headers=self._headers,
                json={"to": to, "messages": messages},
                timeout=self._settings.line_api_timeout,
            )
        except httpx.TransportError as exc:
            log.warning("line_push_transport_error", error=str(exc))
            return False
        if resp.status_code == 200:
            return True
        log.error("line_push_failed", status=resp.status_code, body=resp.text[:200])
        return False

    async def show_loading(self, chat_id: str, seconds: int = 60) -> None:
        """Best-effort typing indicator. Only valid for 1:1 chats — LINE
        rejects group/room ids (upstream called it for groups and swallowed
        the failure on every message)."""
        try:
            resp = await self._client.post(
                f"{LINE_API_BASE}/bot/chat/loading/start",
                headers=self._headers,
                json={"chatId": chat_id, "loadingSeconds": seconds},
                timeout=5,
            )
            if resp.status_code not in (200, 202):
                log.debug("line_loading_failed", status=resp.status_code)
        except httpx.TransportError as exc:
            log.debug("line_loading_transport_error", error=str(exc))

    # ── profile (TTL-cached) ───────────────────────────────────────

    async def get_display_name(self, source: LineSource) -> str | None:
        if not source.user_id:
            return None
        cache_key = f"{source.group_id or source.room_id or ''}:{source.user_id}"
        cached = self._profile_cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and cached[1] > now:
            return cached[0]

        if source.group_id:
            url = f"{LINE_API_BASE}/bot/group/{source.group_id}/member/{source.user_id}"
        elif source.room_id:
            url = f"{LINE_API_BASE}/bot/room/{source.room_id}/member/{source.user_id}"
        else:
            url = f"{LINE_API_BASE}/bot/profile/{source.user_id}"

        name: str | None = None
        try:
            resp = await self._client.get(
                url, headers=self._headers, timeout=self._settings.line_api_timeout
            )
            if resp.status_code == 200:
                name = resp.json().get("displayName")
        except httpx.TransportError as exc:
            log.debug("line_profile_transport_error", error=str(exc))

        if len(self._profile_cache) >= PROFILE_CACHE_MAX_ENTRIES:
            self._profile_cache.pop(next(iter(self._profile_cache)))
        self._profile_cache[cache_key] = (name, now + PROFILE_CACHE_TTL_SECONDS)
        return name

    # ── content download (P5) ──────────────────────────────────────

    async def download_content(self, message_id: str, max_bytes: int) -> tuple[bytes, str]:
        """Streamed download with a hard size cap (upstream buffered unbounded
        resp.content). Returns (data, content_type). Raises ValueError on
        oversize, httpx.HTTPStatusError on non-200."""
        chunks: list[bytes] = []
        total = 0
        async with self._client.stream(
            "GET",
            f"{LINE_DATA_API_BASE}/bot/message/{message_id}/content",
            headers={"Authorization": self._headers["Authorization"]},
            timeout=30,
        ) as resp:
            resp.raise_for_status()
            declared = resp.headers.get("content-length")
            if declared and int(declared) > max_bytes:
                raise ValueError(f"content-length {declared} exceeds cap {max_bytes}")
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"downloaded size exceeds cap {max_bytes}")
                chunks.append(chunk)
            content_type = resp.headers.get("content-type", "application/octet-stream")
        return b"".join(chunks), content_type
