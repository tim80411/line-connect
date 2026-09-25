"""Monthly push quota exhausted: stop asking, keep replying, record the loss."""

import time
from pathlib import Path
from typing import Any

import httpx

from .conftest import (
    DIFY_CHAT_URL,
    asgi_client,
    dify_stream_answer,
    fresh_repo,
    make_settings,
    post_signed,
    running_app,
    text_event,
    webhook_payload,
)

QUOTA_429 = httpx.Response(429, json={"message": "You have reached your monthly limit."})


def dead_token_event(n: int) -> dict[str, Any]:
    """Past LINE's 20-minute cap, so the answer can only go out as a push."""
    return text_event(
        event_id=f"evt-{n}",
        msg_id=f"m-{n}",
        timestamp=int(time.time() * 1000) - 21 * 60_000,
    )


async def inbox_state(tmp_path: Path) -> list[tuple[str, str | None]]:
    async with fresh_repo(tmp_path) as repo:
        with repo._db.locked() as conn:
            rows = conn.execute("SELECT status, last_error FROM inbox ORDER BY id").fetchall()
    return [(r["status"], r["last_error"]) for r in rows]


async def test_undelivered_answer_is_recorded_not_done(tmp_path: Path, mock_apis: Any) -> None:
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["push"].mock(return_value=QUOTA_429)
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()

    assert await inbox_state(tmp_path) == [("delivery_failed", "push_quota_exhausted")]


async def test_quota_refusal_skips_text_only_retry(tmp_path: Path, mock_apis: Any) -> None:
    """The R5 text-only retry is for a batch LINE rejected, not for a quota."""
    mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer("Here!\n![pic](https://cdn.example.com/a.png)", "c-1")
    )
    mock_apis["push"].mock(return_value=QUOTA_429)
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()

    assert mock_apis["push"].call_count == 1


async def test_breaker_stops_push_but_not_reply(tmp_path: Path, mock_apis: Any) -> None:
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["push"].mock(return_value=QUOTA_429)
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(2)))
        await app.state.pipeline.idle()
        fresh = text_event(event_id="evt-3", msg_id="m-3")
        await post_signed(client, settings.webhook_path, webhook_payload(fresh))
        await app.state.pipeline.idle()

    assert mock_apis["push"].call_count == 1, "second push suppressed by the breaker"
    assert mock_apis["reply"].call_count == 1, "free replies keep working"
    assert await inbox_state(tmp_path) == [
        ("delivery_failed", "push_quota_exhausted"),
        ("delivery_failed", "push_quota_exhausted"),
        ("done", None),
    ]


async def test_breaker_probes_again_after_cooldown(tmp_path: Path, mock_apis: Any) -> None:
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["push"].side_effect = [QUOTA_429, httpx.Response(200, json={})]
    settings = make_settings(tmp_path, push_quota_cooldown_seconds=0)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(2)))
        await app.state.pipeline.idle()

    assert mock_apis["push"].call_count == 2
    assert [s for s, _ in await inbox_state(tmp_path)] == ["delivery_failed", "done"]


async def test_rate_limit_is_not_mistaken_for_quota(tmp_path: Path, mock_apis: Any) -> None:
    """A plain 429 is transient: no breaker, and the next answer tries push."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("hi", "c-1"))
    mock_apis["push"].side_effect = [
        httpx.Response(429, json={"message": "Too many requests"}),
        httpx.Response(200, json={}),
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(2)))
        await app.state.pipeline.idle()

    assert mock_apis["push"].call_count == 2
    assert await inbox_state(tmp_path) == [
        ("delivery_failed", "push_failed:429"),
        ("done", None),
    ]


async def test_failed_job_keeps_its_own_error(tmp_path: Path, mock_apis: Any) -> None:
    """When even the apology cannot be delivered, the job still reports why it
    failed in the first place, not the follow-on delivery problem."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=httpx.Response(500, text="boom"))
    mock_apis["push"].mock(return_value=QUOTA_429)
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(dead_token_event(1)))
        await app.state.pipeline.idle()

    [(status, error)] = await inbox_state(tmp_path)
    assert status == "failed"
    assert error is not None and "quota" not in error
