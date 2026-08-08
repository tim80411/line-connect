"""Reply-token strategy (§5.5, §7.5): expired/failed tokens fall back to Push."""

import time
from pathlib import Path
from typing import Any

import httpx

from .conftest import (
    DIFY_CHAT_URL,
    asgi_client,
    dify_stream_answer,
    make_settings,
    post_signed,
    request_json,
    running_app,
    text_event,
    webhook_payload,
)


async def test_reply_400_falls_back_to_push(tmp_path: Path, mock_apis: Any) -> None:
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["reply"].mock(
        return_value=httpx.Response(400, json={"message": "Invalid reply token"})
    )
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

    assert mock_apis["reply"].call_count == 1
    push_route = mock_apis["push"]
    assert push_route.call_count == 1
    body = request_json(push_route, 0)
    assert body["to"] == "U1"
    assert body["messages"][0]["text"] == "hi"


async def test_stale_token_goes_straight_to_push(tmp_path: Path, mock_apis: Any) -> None:
    """Event older than REPLY_TOKEN_TTL: don't waste the doomed reply call."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    settings = make_settings(tmp_path, reply_token_ttl_seconds=50)
    stale_ts = int(time.time() * 1000) - 90_000  # 90s ago
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(timestamp=stale_ts)),
        )
        await app.state.pipeline.idle()

    assert mock_apis["reply"].call_count == 0, "no reply attempt on an expired token"
    assert mock_apis["push"].call_count == 1


async def test_batch_with_bad_image_retries_text_only(tmp_path: Path, mock_apis: Any) -> None:
    """R5 last resort: if the whole batch is rejected, text content still ships."""
    # Dify answers with a markdown image that formatting turns into an image message.
    mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer(
            "Here!\n![pic](https://cdn.example.com/a.png)", "c-1"
        )
    )
    # LINE rejects the mixed batch once (bad image), accepts the text-only retry.
    mock_apis["reply"].mock(return_value=httpx.Response(400, json={"message": "bad"}))
    push_responses = [
        httpx.Response(400, json={"message": "invalid uri"}),
        httpx.Response(200, json={}),
    ]
    mock_apis["push"].side_effect = push_responses
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

    push_route = mock_apis["push"]
    assert push_route.call_count == 2
    retry_body = request_json(push_route, 1)
    assert all(m["type"] == "text" for m in retry_body["messages"])
