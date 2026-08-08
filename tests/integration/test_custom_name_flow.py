"""custom_name changes what the AI is told, not who the AI thinks it is talking to.

Upstream (endpoints/line.py:327-329) derives the Dify end-user id from the
effective name, so renaming a chat in the dashboard silently forks that user's
Dify-side identity and history. We deliberately keep dify_user stable.
"""

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


async def test_custom_name_overrides_display_name_only(
    tmp_path: Path, mock_apis: Any
) -> None:
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("hi", "c-1"),
        dify_stream_answer("hi again", "c-1"),
    ]
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e1", msg_id="m1", text="first")),
        )
        await app.state.pipeline.idle()

        before = request_json(dify_route, 0)
        assert before["inputs"] == {"displayName": "Tim"}
        assert before["user"] == "Tim"

        # What the dashboard's update_chat_meta will do.
        with app.state.db.locked() as conn:
            conn.execute(
                "UPDATE conversations SET custom_name = 'VIP Customer'"
                " WHERE chat_key = 'user:U1'"
            )

        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(text_event(event_id="e2", msg_id="m2", text="second")),
        )
        await app.state.pipeline.idle()

        after = request_json(dify_route, 1)
        assert after["inputs"] == {"displayName": "VIP Customer"}
        assert after["user"] == "Tim", "renaming must not fork the Dify end-user"
        assert after["conversation_id"] == "c-1", "renaming must not start a new chat"

        # The message log keeps the real LINE name so the dashboard can show both.
        with app.state.db.locked() as conn:
            names = [
                r["display_name"]
                for r in conn.execute(
                    "SELECT display_name FROM messages WHERE role = 'user' ORDER BY id"
                )
            ]
        assert names == ["Tim", "Tim"]


async def test_picture_url_stored_from_profile(tmp_path: Path, mock_apis: Any) -> None:
    import httpx

    mock_apis["profile"].mock(
        return_value=httpx.Response(
            200, json={"displayName": "Tim", "pictureUrl": "https://cdn/p.jpg"}
        )
    )
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("ok", "c-1"))
    settings = make_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(client, settings.webhook_path, webhook_payload(text_event()))
        await app.state.pipeline.idle()
        with app.state.db.locked() as conn:
            row = conn.execute(
                "SELECT picture_url, last_message_text, message_count FROM conversations"
                " WHERE chat_key = 'user:U1'"
            ).fetchone()
    assert row["picture_url"] == "https://cdn/p.jpg"
    assert row["last_message_text"] == "hello"
    assert row["message_count"] == 2  # user + bot
