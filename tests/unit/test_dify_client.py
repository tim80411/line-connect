"""Dify client behavior against mocked HTTP (§7.3). The cid-preservation cases
are the regression tests for upstream issue #1."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx

from line_connect.config import Settings
from line_connect.dify.client import ChatResult, DifyClient
from line_connect.dify.errors import DifyFatal, DifyTransient

CHAT_URL = "https://api.dify.ai/v1/chat-messages"


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = dict(
        line_channel_secret="s",
        line_channel_access_token="t",
        dify_api_key="app-key",
        database_path="/tmp/unused.db",  # noqa: S108 — never opened in these tests
    )
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


def ev(
    event: str, answer: str | None = None, cid: str | None = None, **extra: Any
) -> dict[str, Any]:
    data: dict[str, Any] = {"event": event, **extra}
    if answer is not None:
        data["answer"] = answer
    if cid is not None:
        data["conversation_id"] = cid
    return data


def sse_bytes(*events: dict[str, Any]) -> bytes:
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()


def sse_response(*events: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200, content=sse_bytes(*events), headers={"content-type": "text/event-stream"}
    )


class CutStream(httpx.AsyncByteStream):
    """Yields some chunks, then dies like a dropped connection."""

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = chunks

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk
        raise httpx.RemoteProtocolError("peer closed connection without sending complete body")


class CidRecorder:
    def __init__(self) -> None:
        self.cids: list[str] = []
        self.invalidated = 0

    async def on_cid(self, cid: str) -> None:
        self.cids.append(cid)

    async def on_invalid(self) -> None:
        self.invalidated += 1


def request_body(route: respx.Route, call_index: int) -> dict[str, Any]:
    return dict(json.loads(route.calls[call_index].request.content))


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def dify(http_client: httpx.AsyncClient) -> DifyClient:
    return DifyClient(make_settings(), http_client)


@respx.mock
async def test_stream_concatenates_answer_and_captures_cid(dify: DifyClient) -> None:
    respx.post(CHAT_URL).mock(
        return_value=sse_response(
            ev("message", "Hel", cid="c1"),
            ev("message", "lo", cid="c1"),
            ev("message_end", cid="c1"),
        )
    )
    result = await dify.stream_chat("hi", "u1")
    assert result == ChatResult("Hello", "c1")


@respx.mock
async def test_cid_only_in_message_end(dify: DifyClient) -> None:
    rec = CidRecorder()
    respx.post(CHAT_URL).mock(
        return_value=sse_response(ev("message", "Hi"), ev("message_end", cid="c-end"))
    )
    result = await dify.stream_chat("hi", "u1", on_conversation_id=rec.on_cid)
    assert result.conversation_id == "c-end"
    assert rec.cids == ["c-end"]


@respx.mock
async def test_agent_message_events_count(dify: DifyClient) -> None:
    respx.post(CHAT_URL).mock(
        return_value=sse_response(
            ev("agent_message", "A"), ev("agent_message", "B"), ev("message_end", cid="c1")
        )
    )
    result = await dify.stream_chat("hi", "u1")
    assert result.answer == "AB"


@respx.mock
async def test_midstream_cut_returns_partial_and_cid_was_written_early(
    dify: DifyClient,
) -> None:
    """The stream dies after the first chunk. The partial answer is delivered
    AND the cid callback already fired — proving the early write happens before
    stream completion (issue #1 root cause #2)."""
    rec = CidRecorder()
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200,
            stream=CutStream(sse_bytes(ev("message", "partial answer", cid="c-early"))),
            headers={"content-type": "text/event-stream"},
        )
    )
    result = await dify.stream_chat("hi", "u1", on_conversation_id=rec.on_cid)
    assert result == ChatResult("partial answer", "c-early")
    assert rec.cids == ["c-early"], "cid must be persisted before the stream ends"


@respx.mock
async def test_immediate_cut_without_partial_raises_transient(dify: DifyClient) -> None:
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200, stream=CutStream(), headers={"content-type": "text/event-stream"}
        )
    )
    with pytest.raises(DifyTransient):
        await dify.stream_chat("hi", "u1")


@respx.mock
async def test_sse_error_event_is_fatal(dify: DifyClient) -> None:
    respx.post(CHAT_URL).mock(
        return_value=sse_response(ev("error", message="App unavailable"))
    )
    with pytest.raises(DifyFatal):
        await dify.stream_chat("hi", "u1")


@respx.mock
async def test_chat_404_drops_cid_and_retries_without_it(dify: DifyClient) -> None:
    rec = CidRecorder()
    route = respx.post(CHAT_URL)
    route.side_effect = [
        httpx.Response(404, json={"code": "not_found", "message": "Conversation Not Exists."}),
        sse_response(ev("message", "fresh start", cid="c-new"), ev("message_end", cid="c-new")),
    ]
    result = await dify.chat(
        "hi",
        "u1",
        conversation_id="c-stale",
        on_conversation_id=rec.on_cid,
        on_conversation_invalid=rec.on_invalid,
    )
    assert result.answer == "fresh start"
    assert rec.invalidated == 1
    assert request_body(route, 0)["conversation_id"] == "c-stale"
    assert "conversation_id" not in request_body(route, 1), "retry must NOT carry the stale cid"


@respx.mock
async def test_chat_transient_falls_back_to_blocking_with_same_cid(dify: DifyClient) -> None:
    """Issue #1 regression: a 500 on the stream must NOT reset the conversation."""
    rec = CidRecorder()
    route = respx.post(CHAT_URL)
    route.side_effect = [
        httpx.Response(500, text="upstream hiccup"),
        httpx.Response(200, json={"answer": "still here", "conversation_id": "c-keep"}),
    ]
    result = await dify.chat(
        "hi",
        "u1",
        conversation_id="c-keep",
        on_conversation_id=rec.on_cid,
        on_conversation_invalid=rec.on_invalid,
    )
    assert result == ChatResult("still here", "c-keep")
    assert rec.invalidated == 0, "transient error must never clear the cid"
    second = request_body(route, 1)
    assert second["response_mode"] == "blocking"
    assert second["conversation_id"] == "c-keep", "blocking retry must keep the cid"


@respx.mock
async def test_chat_blocking_404_clears_and_retries_blocking(dify: DifyClient) -> None:
    rec = CidRecorder()
    route = respx.post(CHAT_URL)
    route.side_effect = [
        httpx.Response(500, text="stream down"),
        httpx.Response(404, json={"message": "Conversation Not Exists."}),
        httpx.Response(200, json={"answer": "new conv", "conversation_id": "c-new"}),
    ]
    result = await dify.chat(
        "hi",
        "u1",
        conversation_id="c-stale",
        on_conversation_invalid=rec.on_invalid,
    )
    assert result.answer == "new conv"
    assert rec.invalidated == 1
    assert "conversation_id" not in request_body(route, 2)


@respx.mock
async def test_chat_double_transient_gives_up_but_keeps_cid(dify: DifyClient) -> None:
    rec = CidRecorder()
    route = respx.post(CHAT_URL)
    route.side_effect = [
        httpx.Response(500, text="stream down"),
        httpx.Response(503, text="blocking down too"),
    ]
    with pytest.raises(DifyTransient):
        await dify.chat(
            "hi", "u1", conversation_id="c-keep", on_conversation_invalid=rec.on_invalid
        )
    assert rec.invalidated == 0, "giving up must not reset the conversation"
    assert len(route.calls) == 2


@respx.mock
async def test_chat_fatal_no_retry(dify: DifyClient) -> None:
    route = respx.post(CHAT_URL)
    route.side_effect = [httpx.Response(401, json={"code": "unauthorized"})]
    with pytest.raises(DifyFatal):
        await dify.chat("hi", "u1", conversation_id="c1")
    assert len(route.calls) == 1


@respx.mock
async def test_chat_404_without_cid_propagates(dify: DifyClient) -> None:
    """No cid to drop → a 404 is a real error, not a reset trigger."""
    respx.post(CHAT_URL).mock(return_value=httpx.Response(404, json={"code": "not_found"}))
    with pytest.raises(Exception, match="404"):
        await dify.chat("hi", "u1", conversation_id=None)


@respx.mock
async def test_blocking_chat_fires_cid_callback(dify: DifyClient) -> None:
    rec = CidRecorder()
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, json={"answer": "ok", "conversation_id": "c-b"})
    )
    result = await dify.blocking_chat("hi", "u1", on_conversation_id=rec.on_cid)
    assert result == ChatResult("ok", "c-b")
    assert rec.cids == ["c-b"]


@respx.mock
async def test_connect_error_is_transient(dify: DifyClient) -> None:
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(DifyTransient):
        await dify.stream_chat("hi", "u1")
