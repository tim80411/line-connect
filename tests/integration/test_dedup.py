"""LINE redelivers webhooks; the same event must be processed exactly once (§7.5)."""

from pathlib import Path

from line_connect.storage.repository import InboxJob

from .conftest import (
    asgi_client,
    make_settings,
    post_signed,
    running_app,
    text_event,
    webhook_payload,
)


async def test_same_webhook_event_id_processed_once(tmp_path: Path) -> None:
    calls: list[InboxJob] = []

    async def handler(job: InboxJob) -> None:
        calls.append(job)

    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        payload = webhook_payload(text_event(event_id="evt-dup"))
        first = await post_signed(client, settings.webhook_path, payload)
        second = await post_signed(client, settings.webhook_path, payload)
        assert first.status_code == second.status_code == 200

        await app.state.pipeline.idle()
        assert len(calls) == 1
        assert app.state.repo.count_by_status() == {"done": 1}


async def test_fallback_dedup_key_uses_message_id(tmp_path: Path) -> None:
    """Without webhookEventId (older payloads), msg:<id> still dedups."""
    calls: list[InboxJob] = []

    async def handler(job: InboxJob) -> None:
        calls.append(job)

    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        payload = webhook_payload(text_event(event_id=None, msg_id="m-77"))
        await post_signed(client, settings.webhook_path, payload)
        await post_signed(client, settings.webhook_path, payload)

        await app.state.pipeline.idle()
        assert len(calls) == 1
        assert calls[0].dedup_key == "msg:m-77"


async def test_distinct_events_both_processed(tmp_path: Path) -> None:
    calls: list[InboxJob] = []

    async def handler(job: InboxJob) -> None:
        calls.append(job)

    settings = make_settings(tmp_path)
    async with running_app(settings, handler=handler) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(
                text_event(event_id="evt-1", msg_id="m-1"),
                text_event(event_id="evt-2", msg_id="m-2"),
            ),
        )
        await app.state.pipeline.idle()
        assert len(calls) == 2
