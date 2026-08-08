"""Async Dify chat-messages client.

Two things here fix issue #1 and must not be "simplified" away:

1. `on_conversation_id` fires the moment the first SSE chunk carries a
   conversation_id. Dify has already created the conversation at that point;
   waiting for the stream to finish (upstream did) meant any interruption
   orphaned the conversation.

2. `chat()` retries by error class, not blindly: transient errors switch
   transport but keep the cid; only DifyConversationInvalid drops it, via the
   `on_conversation_invalid` callback so the caller can clear its store.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from line_connect.config import Settings
from line_connect.dify.errors import (
    DifyConversationInvalid,
    DifyFatal,
    DifyTransient,
    classify_http_status,
    classify_transport_error,
)

log = structlog.get_logger(__name__)

CidCallback = Callable[[str], Awaitable[None]]
InvalidCidCallback = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class ChatResult:
    answer: str
    conversation_id: str | None


def build_payload(
    inputs: dict[str, Any] | None,
    query: str,
    user: str,
    conversation_id: str | None,
    response_mode: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "inputs": inputs or {},
        "query": query,
        "response_mode": response_mode,
        "user": user,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    return payload


class DifyClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client
        self._chat_url = f"{settings.dify_api_base_url}/chat-messages"
        self._headers = {
            "Authorization": f"Bearer {settings.dify_api_key}",
            "Content-Type": "application/json",
        }

    # ── orchestration (plan §5.3) ──────────────────────────────────

    async def chat(
        self,
        query: str,
        user: str,
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        on_conversation_id: CidCallback | None = None,
        on_conversation_invalid: InvalidCidCallback | None = None,
    ) -> ChatResult:
        try:
            return await self.stream_chat(
                query, user, inputs, conversation_id, on_conversation_id
            )
        except DifyConversationInvalid:
            if not conversation_id:
                raise
            log.warning("conversation_invalid_reset", user=user[:12])
            if on_conversation_invalid is not None:
                await on_conversation_invalid()
            return await self.stream_chat(query, user, inputs, None, on_conversation_id)
        except DifyTransient as stream_exc:
            log.warning("stream_failed_try_blocking", error=str(stream_exc)[:200])
            try:
                return await self.blocking_chat(
                    query, user, inputs, conversation_id, on_conversation_id
                )
            except DifyConversationInvalid:
                if not conversation_id:
                    raise
                log.warning("conversation_invalid_reset_blocking", user=user[:12])
                if on_conversation_invalid is not None:
                    await on_conversation_invalid()
                return await self.blocking_chat(query, user, inputs, None, on_conversation_id)
            # A second DifyTransient propagates: give up, notify user, cid untouched.

    # ── transports ─────────────────────────────────────────────────

    async def stream_chat(
        self,
        query: str,
        user: str,
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        on_conversation_id: CidCallback | None = None,
    ) -> ChatResult:
        payload = build_payload(inputs, query, user, conversation_id, "streaming")
        timeout = httpx.Timeout(
            connect=self._settings.dify_connect_timeout,
            read=self._settings.dify_stream_read_timeout,  # gap between chunks
            write=self._settings.dify_connect_timeout,
            pool=self._settings.dify_connect_timeout,
        )
        answer_parts: list[str] = []
        cid: str | None = None
        try:
            async with self._client.stream(
                "POST", self._chat_url, json=payload, headers=self._headers, timeout=timeout
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise classify_http_status(
                        resp.status_code, body, self._settings.conversation_error_marker_list
                    )
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    event = data.get("event")
                    if event in ("message", "agent_message"):
                        answer_parts.append(data.get("answer", ""))
                    elif event == "error":
                        raise DifyFatal(
                            f"Dify error event: {data.get('message', 'Unknown')[:300]}"
                        )
                    elif event != "message_end":
                        continue
                    new_cid = data.get("conversation_id")
                    if new_cid and cid is None and on_conversation_id is not None:
                        # First sighting: Dify has created the conversation.
                        # Persist NOW, before anything can interrupt the stream.
                        await on_conversation_id(new_cid)
                    if new_cid:
                        cid = new_cid
        except httpx.TransportError as exc:
            partial = "".join(answer_parts)
            if partial:
                # Mid-stream cut with usable content: deliver it (upstream semantic).
                log.warning("stream_cut_partial", partial_len=len(partial), error=str(exc))
                return ChatResult(partial, cid)
            raise classify_transport_error(exc) from exc
        return ChatResult("".join(answer_parts), cid)

    async def upload_file(
        self, filename: str, content: bytes, mimetype: str, user: str
    ) -> dict[str, Any] | None:
        """POST /files/upload. Returns the file info dict or None on failure
        (upstream semantic: media failures are soft errors)."""
        try:
            resp = await self._client.post(
                f"{self._settings.dify_api_base_url}/files/upload",
                headers={"Authorization": self._headers["Authorization"]},
                files={"file": (filename, content, mimetype)},
                data={"user": user},
                timeout=60,
            )
        except httpx.TransportError as exc:
            log.error("dify_upload_transport_error", error=str(exc))
            return None
        if resp.status_code in (200, 201):
            data: dict[str, Any] = resp.json()
            return data
        log.error("dify_upload_failed", status=resp.status_code, body=resp.text[:300])
        return None

    async def blocking_chat(
        self,
        query: str,
        user: str,
        inputs: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        on_conversation_id: CidCallback | None = None,
    ) -> ChatResult:
        payload = build_payload(inputs, query, user, conversation_id, "blocking")
        try:
            resp = await self._client.post(
                self._chat_url,
                json=payload,
                headers=self._headers,
                timeout=self._settings.dify_blocking_timeout,
            )
        except httpx.TransportError as exc:
            raise classify_transport_error(exc) from exc
        if resp.status_code != 200:
            raise classify_http_status(
                resp.status_code, resp.text, self._settings.conversation_error_marker_list
            )
        data = resp.json()
        cid = data.get("conversation_id") or None
        if cid and on_conversation_id is not None:
            await on_conversation_id(cid)
        return ChatResult(data.get("answer", ""), cid)
