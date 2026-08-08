"""The webhook must ack instantly and never do business work inline (§7.5)."""

import asyncio
import time
from pathlib import Path
from typing import Any

from line_connect.storage.repository import InboxJob

from .conftest import (
    asgi_client,
    make_settings,
    post_signed,
    running_app,
    text_event,
    webhook_payload,
)


async def test_ack_before_processing(tmp_path: Path) -> None:
    """200 returns while the (slow) handler has not even started."""
    started = asyncio.Event()
    calls: list[InboxJob] = []

    async def slow_handler(job: InboxJob) -> None:
        started.set()
        await asyncio.sleep(0.3)
        calls.append(job)

    settings = make_settings(tmp_path)
    async with running_app(settings, handler=slow_handler) as app, asgi_client(app) as client:
        t0 = time.perf_counter()
        resp = await post_signed(
            client, settings.webhook_path, webhook_payload(text_event())
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert resp.status_code == 200
        assert elapsed_ms < 100, f"ack took {elapsed_ms:.0f}ms"
        assert not calls, "handler finished before webhook returned"

        await app.state.pipeline.idle()
        assert len(calls) == 1
        assert calls[0].chat_key == "user:U1"
    assert started.is_set()


async def test_bad_signature_rejected(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        resp = await client.post(
            settings.webhook_path,
            content=b'{"events": []}',
            headers={"X-Line-Signature": "AAAA_invalid"},
        )
        assert resp.status_code == 400


async def test_missing_signature_rejected(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        resp = await client.post(settings.webhook_path, content=b'{"events": []}')
        assert resp.status_code == 400


async def test_empty_events_ok(tmp_path: Path) -> None:
    """LINE console 'Verify' sends an empty events array."""
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        resp = await post_signed(client, settings.webhook_path, webhook_payload())
        assert resp.status_code == 200


async def test_empty_body_ok(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        resp = await client.post(settings.webhook_path, content=b"")
        assert resp.status_code == 200


async def test_unhandled_event_types_ignored(tmp_path: Path) -> None:
    calls: list[Any] = []

    async def handler(job: InboxJob) -> None:
        calls.append(job)

    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        unfollow = {
            "type": "unfollow",
            "timestamp": 1,
            "source": {"type": "user", "userId": "U1"},
            "webhookEventId": "evt-unfollow",
        }
        resp = await post_signed(
            client, settings.webhook_path, webhook_payload(unfollow)
        )
        assert resp.status_code == 200
        await app.state.pipeline.idle()
        assert calls == []
