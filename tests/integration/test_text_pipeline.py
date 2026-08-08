"""End-to-end text flow with the real Bridge: webhook → queue → Dify → LINE (§7.5)."""

from pathlib import Path
from typing import Any

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


async def test_text_roundtrip(tmp_path: Path, mock_apis: Any) -> None:
    dify_route = mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer("Hello Tim!", "c-1")
    )
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

        assert dify_route.call_count == 1
        dify_body = request_json(dify_route, 0)
        assert dify_body["query"] == "hello"
        assert dify_body["inputs"] == {"displayName": "Tim"}
        assert "conversation_id" not in dify_body  # first contact

        reply_route = mock_apis["reply"]
        assert reply_route.call_count == 1
        reply_body = request_json(reply_route, 0)
        assert reply_body["messages"] == [{"type": "text", "text": "Hello Tim!"}]

        assert app.state.repo.count_by_status() == {"done": 1}
        with app.state.db.locked() as conn:
            msgs = conn.execute(
                "SELECT role, text, conversation_id FROM messages ORDER BY id"
            ).fetchall()
        assert [(m["role"], m["text"]) for m in msgs] == [
            ("user", "hello"),
            ("bot", "Hello Tim!"),
        ]
        assert msgs[1]["conversation_id"] == "c-1"


async def test_follow_sends_welcome(tmp_path: Path, mock_apis: Any) -> None:
    settings = make_settings(tmp_path, welcome_message="Hi there!")
    follow = {
        "type": "follow",
        "timestamp": 1,
        "webhookEventId": "evt-follow-1",
        "source": {"type": "user", "userId": "U1"},
        "replyToken": "rt-follow",
    }
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(follow))
        await app.state.pipeline.idle()

    # Fresh reply token missing a timestamp check falls to push; either channel
    # is acceptable delivery for a welcome — but exactly one send must happen.
    reply_route, push_route = mock_apis["reply"], mock_apis["push"]
    assert reply_route.call_count + push_route.call_count == 1
    sent_route = reply_route if reply_route.call_count else push_route
    body = request_json(sent_route, 0)
    assert body["messages"] == [{"type": "text", "text": "Hi there!"}]


async def test_empty_answer_gets_fallback_text(tmp_path: Path, mock_apis: Any) -> None:
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("", "c-1"))
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()

    reply_route = mock_apis["reply"]
    assert reply_route.call_count == 1
    body = request_json(reply_route, 0)
    assert "couldn't generate" in body["messages"][0]["text"]


async def test_loading_indicator_only_for_direct_chats(tmp_path: Path, mock_apis: Any) -> None:
    """Group messages must not hit the loading API (LINE rejects group ids —
    upstream bug)."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("ok", "c-g"))
    mock_apis.get(
        "https://api.line.me/v2/bot/group/G9/member/U1", name="group_profile"
    ).mock(return_value=httpx_response_profile())
    settings = make_settings(tmp_path)
    group_event = text_event(event_id="evt-group", msg_id="m-group")
    group_event["source"] = {"type": "group", "groupId": "G9", "userId": "U1"}
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(group_event))
        await app.state.pipeline.idle()

    assert mock_apis["loading"].call_count == 0


def httpx_response_profile() -> Any:
    import httpx

    return httpx.Response(200, json={"displayName": "GroupTim"})
