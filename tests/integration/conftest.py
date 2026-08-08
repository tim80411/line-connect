"""Shared fixtures for integration tests: real SQLite, in-process ASGI app,
signed webhook payloads."""

import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from line_connect.config import Settings
from line_connect.line.signature import compute_signature
from line_connect.main import create_app
from line_connect.pipeline.queue import FailureHook, Handler
from line_connect.storage.db import Database
from line_connect.storage.repository import Repository

TEST_SECRET = "test-channel-secret"


@asynccontextmanager
async def fresh_repo(tmp_path: Path) -> AsyncIterator[Repository]:
    """Post-mortem DB inspection after an app's lifespan has closed its connection."""
    db = Database(str(tmp_path / "app.db"))
    db.connect()
    try:
        yield Repository(db)
    finally:
        db.close()


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    defaults: dict[str, Any] = dict(
        line_channel_secret=TEST_SECRET,
        line_channel_access_token="test-line-token",
        dify_api_key="app-test-key",
        database_path=str(tmp_path / "app.db"),
        worker_count=2,
        drain_delay_seconds=0,
        shutdown_grace_seconds=2,
        log_format="console",
    )
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


@asynccontextmanager
async def running_app(
    settings: Settings,
    handler: Handler | None = None,
    on_failure: FailureHook | None = None,
) -> AsyncIterator[FastAPI]:
    app = create_app(settings, handler=handler, on_failure=on_failure)
    async with app.router.lifespan_context(app):
        yield app


def asgi_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


async def post_signed(
    client: httpx.AsyncClient, path: str, payload: dict[str, Any]
) -> httpx.Response:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return await client.post(
        path,
        content=body,
        headers={
            "X-Line-Signature": compute_signature(TEST_SECRET, body),
            "Content-Type": "application/json",
        },
    )


def text_event(
    user_id: str = "U1",
    text: str = "hello",
    event_id: str | None = "evt-0001",
    msg_id: str = "m-0001",
    reply_token: str | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """timestamp defaults to 'now' so reply tokens look fresh to the replier;
    reply_token defaults to one unique per message (LINE reality — the replier
    refuses to reuse a consumed token)."""
    event: dict[str, Any] = {
        "type": "message",
        "timestamp": timestamp if timestamp is not None else int(time.time() * 1000),
        "source": {"type": "user", "userId": user_id},
        "replyToken": reply_token if reply_token is not None else f"rt-{msg_id}",
        "deliveryContext": {"isRedelivery": False},
        "message": {"id": msg_id, "type": "text", "text": text},
    }
    if event_id is not None:
        event["webhookEventId"] = event_id
    return event


def webhook_payload(*events: dict[str, Any]) -> dict[str, Any]:
    return {"destination": "xxx", "events": list(events)}


@pytest.fixture
def recording_handler() -> tuple[Handler, list[Any]]:
    calls: list[Any] = []

    async def handler(job: Any) -> None:
        calls.append(job)

    return handler, calls


Recorder = Callable[[], tuple[Handler, list[Any]]]


# ── LINE / Dify HTTP mocks (real Bridge handler) ───────────────────

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_LOADING_URL = "https://api.line.me/v2/bot/chat/loading/start"
LINE_PROFILE_URL = "https://api.line.me/v2/bot/profile/U1"
DIFY_CHAT_URL = "https://api.dify.ai/v1/chat-messages"
DIFY_UPLOAD_URL = "https://api.dify.ai/v1/files/upload"


def line_content_url(msg_id: str) -> str:
    return f"https://api-data.line.me/v2/bot/message/{msg_id}/content"


def media_event(
    msg_type: str = "image",
    msg_id: str = "m-media-1",
    event_id: str = "evt-media-1",
    user_id: str = "U1",
    reply_token: str = "rt-media-1",
    file_name: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"id": msg_id, "type": msg_type}
    if file_name is not None:
        message["fileName"] = file_name
    return {
        "type": "message",
        "timestamp": int(time.time() * 1000),
        "webhookEventId": event_id,
        "source": {"type": "user", "userId": user_id},
        "replyToken": reply_token,
        "deliveryContext": {"isRedelivery": False},
        "message": message,
    }


def sse_event(event: str, answer: str | None = None, cid: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"event": event}
    if answer is not None:
        data["answer"] = answer
    if cid is not None:
        data["conversation_id"] = cid
    return data


def sse_response(*events: dict[str, Any]) -> httpx.Response:
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()
    return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})


def dify_stream_answer(answer: str, cid: str) -> httpx.Response:
    return sse_response(
        sse_event("message", answer, cid), sse_event("message_end", cid=cid)
    )


def request_json(route: Any, call_index: int) -> dict[str, Any]:
    return dict(json.loads(route.calls[call_index].request.content))


@pytest.fixture
def mock_apis() -> AsyncIterator[Any]:
    """respx router with LINE endpoints stubbed OK. Dify route left to tests.

    Intercepts only real-transport clients — the ASGI test client is untouched.
    """
    import respx

    with respx.mock(assert_all_called=False) as router:
        router.post(LINE_REPLY_URL, name="reply").mock(
            return_value=httpx.Response(200, json={})
        )
        router.post(LINE_PUSH_URL, name="push").mock(
            return_value=httpx.Response(200, json={})
        )
        router.post(LINE_LOADING_URL, name="loading").mock(
            return_value=httpx.Response(202, json={})
        )
        router.get(LINE_PROFILE_URL, name="profile").mock(
            return_value=httpx.Response(200, json={"displayName": "Tim"})
        )
        yield router
