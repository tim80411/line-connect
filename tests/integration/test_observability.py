"""Delivery-path telemetry: the log lines that let reply hit rate and webhook
redelivery be measured from production logs (uvicorn runs with no access log)."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from line_connect.api import webhook as webhook_module
from line_connect.pipeline import queue as queue_module
from line_connect.pipeline import replier as replier_module

from ..conftest import RecordingLogger
from .conftest import (
    DIFY_CHAT_URL,
    asgi_client,
    dify_stream_answer,
    make_settings,
    post_signed,
    running_app,
    text_event,
    webhook_payload,
)

RecordLogs = Callable[[Any], RecordingLogger]


async def test_reply_delivery_is_logged(
    tmp_path: Path, mock_apis: Any, record_logs: RecordLogs
) -> None:
    replier_log = record_logs(replier_module)
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

    [delivered] = replier_log.events("delivered")
    assert delivered["via"] == "reply"
    assert delivered["reply_skip"] is None
    assert delivered["token_age_ms"] is not None


async def test_push_delivery_records_why_reply_was_skipped(
    tmp_path: Path, mock_apis: Any, record_logs: RecordLogs
) -> None:
    replier_log = record_logs(replier_module)
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["reply"].mock(
        return_value=httpx.Response(400, json={"message": "Invalid reply token"})
    )
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

    [delivered] = replier_log.events("delivered")
    assert delivered["via"] == "push"
    assert delivered["reply_skip"] == "reply_rejected"


async def test_claim_logs_redelivery_and_arrival_age(
    tmp_path: Path, record_logs: RecordLogs, recording_handler: Any
) -> None:
    """A claimed redelivery = LINE's first attempt never reached the app."""
    queue_log = record_logs(queue_module)
    handler, _ = recording_handler
    event = text_event(timestamp=int(time.time() * 1000) - 64_000)
    event["deliveryContext"] = {"isRedelivery": True}
    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(event))
        await app.state.pipeline.idle()

    [claimed] = queue_log.events("event_claimed")
    assert claimed["redelivery"] is True
    assert 64_000 <= claimed["event_age_ms"] < 70_000


async def test_webhook_logs_every_request_outcome(
    tmp_path: Path, record_logs: RecordLogs, recording_handler: Any
) -> None:
    webhook_log = record_logs(webhook_module)
    handler, _ = recording_handler
    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        payload = webhook_payload(text_event())
        await post_signed(client, settings.webhook_path, payload)
        await post_signed(client, settings.webhook_path, payload)  # duplicate
        await client.post(
            settings.webhook_path,
            content=b'{"events": []}',
            headers={"X-Line-Signature": "AAAA_invalid"},
        )
        await app.state.pipeline.idle()

    handled = webhook_log.events("webhook_handled")
    assert [(h["events"], h["claimed"]) for h in handled] == [(1, 1), (1, 0)]
    assert all(isinstance(h["handler_ms"], int) for h in handled)
    [rejected] = webhook_log.events("webhook_rejected")
    assert rejected["reason"] == "invalid_signature"
