"""Conversation continuity — the issue #1 acceptance tests (§7.5)."""

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


async def test_cid_persisted_and_reused(tmp_path: Path, mock_apis: Any) -> None:
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("first", "c-1"),
        dify_stream_answer("second", "c-1"),
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e1", msg_id="m1", text="one")),
        )
        await app.state.pipeline.idle()
        assert app.state.repo.get_cid("user:U1") == "c-1"

        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e2", msg_id="m2", text="two")),
        )
        await app.state.pipeline.idle()

    assert "conversation_id" not in request_json(dify_route, 0)
    assert request_json(dify_route, 1)["conversation_id"] == "c-1"


async def test_transient_error_does_not_clear_cid(tmp_path: Path, mock_apis: Any) -> None:
    """Issue #1 regression: stream 500 + blocking 500 = total failure, user is
    notified, and the cid SURVIVES for the next message."""
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("hi", "c-keep"),   # msg 1: establishes cid
        httpx.Response(500, text="stream down"),    # msg 2: stream fails
        httpx.Response(503, text="blocking down"),  # msg 2: blocking fails too
        dify_stream_answer("back", "c-keep"),  # msg 3: recovered
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        for i, text in ((1, "one"), (2, "two"), (3, "three")):
            await post_signed(
                client,
                settings.webhook_path,
                webhook_payload(text_event(event_id=f"e{i}", msg_id=f"m{i}", text=text)),
            )
            await app.state.pipeline.idle()

        assert app.state.repo.get_cid("user:U1") == "c-keep", (
            "a transient outage must never reset the conversation"
        )
        statuses = app.state.repo.count_by_status()
        assert statuses == {"done": 2, "failed": 1}

    # msg 2's two attempts both carried the cid; msg 3 still carries it.
    assert request_json(dify_route, 1)["conversation_id"] == "c-keep"
    assert request_json(dify_route, 2)["conversation_id"] == "c-keep"
    assert request_json(dify_route, 3)["conversation_id"] == "c-keep"
    # The user got exactly one error notification (dedup window).
    total_sends = mock_apis["reply"].call_count + mock_apis["push"].call_count
    assert total_sends == 3  # answer1 + error notice + answer3


async def test_conversation_invalid_resets_cid(tmp_path: Path, mock_apis: Any) -> None:
    """Dify explicitly reports the conversation gone → new one is started and
    the fresh cid replaces the stale one."""
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("hi", "c-old"),
        httpx.Response(404, json={"message": "Conversation Not Exists."}),
        dify_stream_answer("fresh", "c-new"),
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        for i in (1, 2):
            await post_signed(
                client,
                settings.webhook_path,
                webhook_payload(text_event(event_id=f"e{i}", msg_id=f"m{i}")),
            )
            await app.state.pipeline.idle()

        assert app.state.repo.get_cid("user:U1") == "c-new"
    assert "conversation_id" not in request_json(dify_route, 2)


async def test_clear_command(tmp_path: Path, mock_apis: Any) -> None:
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("hi", "c-1"),
        dify_stream_answer("clean slate", "c-2"),
    ]
    settings = make_settings(tmp_path, clear_confirm_message="Cleared!")
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e1", msg_id="m1", text="hello")),
        )
        await app.state.pipeline.idle()
        assert app.state.repo.get_cid("user:U1") == "c-1"

        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e2", msg_id="m2", text="/clear")),
        )
        await app.state.pipeline.idle()
        assert app.state.repo.get_cid("user:U1") is None
        with app.state.db.locked() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM conversations WHERE chat_key = 'user:U1'"
            ).fetchone()
        assert row["n"] == 0, "/clear must delete the conversation row"

        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e3", msg_id="m3", text="again")),
        )
        await app.state.pipeline.idle()

    # Dify was NOT called for /clear itself.
    assert dify_route.call_count == 2
    assert "conversation_id" not in request_json(dify_route, 1)
    reply_bodies = [
        request_json(mock_apis["reply"], i)
        for i in range(mock_apis["reply"].call_count)
    ]
    assert any(
        b["messages"][0]["text"] == "Cleared!" for b in reply_bodies
    ), "user must get the clear confirmation"


async def test_same_chat_sequential_cid_chain(tmp_path: Path, mock_apis: Any) -> None:
    """Two messages posted in one webhook batch: the second must carry the cid
    the first created (per-chat FIFO prevents forked conversations)."""
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("A", "c-chain"),
        dify_stream_answer("B", "c-chain"),
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(
                text_event(event_id="e1", msg_id="m1", text="first"),
                text_event(event_id="e2", msg_id="m2", text="second"),
            ),
        )
        await app.state.pipeline.idle()

    assert request_json(dify_route, 0)["query"] == "first"
    assert "conversation_id" not in request_json(dify_route, 0)
    second = request_json(dify_route, 1)
    assert second["query"] == "second"
    assert second["conversation_id"] == "c-chain", (
        "second message must continue the conversation the first one created"
    )
