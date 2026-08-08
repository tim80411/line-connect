"""P6 hardening: job timeout, 50-message flood, secret leakage audit."""

import asyncio
from pathlib import Path
from typing import Any

from line_connect.storage.repository import InboxJob

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


async def test_job_timeout_marks_failed_and_notifies(
    tmp_path: Path, mock_apis: Any
) -> None:
    async def stuck_handler(job: InboxJob) -> None:
        await asyncio.sleep(30)

    settings = make_settings(tmp_path, job_timeout_seconds=0.1)
    async with running_app(settings, handler=stuck_handler) as app, asgi_client(
        app
    ) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()
        assert app.state.repo.count_by_status() == {"failed": 1}

    sends = mock_apis["reply"].call_count + mock_apis["push"].call_count
    assert sends == 1, "user must hear about the timeout exactly once"
    route = mock_apis["reply"] if mock_apis["reply"].call_count else mock_apis["push"]
    assert "too long" in request_json(route, 0)["messages"][0]["text"]


async def test_flood_50_messages_no_loss_ordered(tmp_path: Path, mock_apis: Any) -> None:
    """Two chats × 25 messages, real Bridge, mocked APIs: nothing lost, strict
    per-chat ordering, one reply per message."""
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer(f"ans-{i}", "c-flood") for i in range(50)
    ]
    mock_apis.get("https://api.line.me/v2/bot/profile/U2", name="profile2").mock(
        return_value=__import__("httpx").Response(200, json={"displayName": "Ann"})
    )
    settings = make_settings(tmp_path, worker_count=4)
    async with running_app(settings) as app, asgi_client(app) as client:
        events = []
        for i in range(25):
            events.append(
                text_event(
                    user_id="U1", text=f"u1-{i}", event_id=f"e-u1-{i}", msg_id=f"m-u1-{i}"
                )
            )
            events.append(
                text_event(
                    user_id="U2", text=f"u2-{i}", event_id=f"e-u2-{i}", msg_id=f"m-u2-{i}"
                )
            )
        # Send in 5 webhook batches of 20, like LINE would.
        for start in range(0, 50, 20):
            await post_signed(
                client,
                settings.webhook_path,
                webhook_payload(*events[start : start + 20]),
            )
        await app.state.pipeline.idle()

        assert app.state.repo.count_by_status() == {"done": 50}, "no job lost"

    assert dify_route.call_count == 50
    queries = [request_json(dify_route, i)["query"] for i in range(50)]
    u1_order = [q for q in queries if q.startswith("u1-")]
    u2_order = [q for q in queries if q.startswith("u2-")]
    assert u1_order == [f"u1-{i}" for i in range(25)], "per-chat FIFO violated for U1"
    assert u2_order == [f"u2-{i}" for i in range(25)], "per-chat FIFO violated for U2"
    deliveries = mock_apis["reply"].call_count + mock_apis["push"].call_count
    assert deliveries == 50, "one delivery per message"


async def test_secrets_never_reach_logs(
    tmp_path: Path, mock_apis: Any, capfd: Any
) -> None:
    """Run a real round trip, then grep everything the app printed for the
    channel token / API key values."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    secret_values = ("super-secret-channel", "super-secret-line-token", "app-super-secret")
    settings = make_settings(
        tmp_path,
        line_channel_secret=secret_values[0],
        line_channel_access_token=secret_values[1],
        dify_api_key=secret_values[2],
        log_level="DEBUG",
    )
    async with running_app(settings) as app, asgi_client(app) as client:
        body = webhook_payload(text_event())
        import json as _json

        from line_connect.line.signature import compute_signature

        raw = _json.dumps(body).encode()
        await client.post(
            settings.webhook_path,
            content=raw,
            headers={"X-Line-Signature": compute_signature(secret_values[0], raw)},
        )
        await app.state.pipeline.idle()

    captured = capfd.readouterr()
    all_output = captured.out + captured.err
    for secret in secret_values:
        assert secret not in all_output, f"secret value leaked into logs: {secret[:8]}…"
