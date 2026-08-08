"""Admin API end-to-end: login, token auth, chat list/history/meta."""

from pathlib import Path
from typing import Any

import httpx
import pytest

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

ADMIN_PASSWORD = "s3cret-pw"


def admin_settings(tmp_path: Path, **overrides: Any) -> Any:
    return make_settings(tmp_path, admin_password=ADMIN_PASSWORD, **overrides)


async def call(
    client: httpx.AsyncClient, action: str, token: str | None = None, **params: Any
) -> httpx.Response:
    body: dict[str, Any] = {"action": action, **params}
    if token is not None:
        body["token"] = token
    return await client.post("/admin", json=body)


async def login(client: httpx.AsyncClient, password: str = ADMIN_PASSWORD) -> str:
    resp = await call(client, "login", password=password)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


async def seed_chat(client: httpx.AsyncClient, settings: Any, app: Any, **kw: Any) -> None:
    await post_signed(client, settings.webhook_path, webhook_payload(text_event(**kw)))
    await app.state.pipeline.idle()


# ── mounting ───────────────────────────────────────────────────────


async def test_admin_absent_without_password(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)  # no admin_password
    async with running_app(settings) as app, asgi_client(app) as client:
        assert (await client.get("/admin")).status_code == 404
        assert (await client.post("/admin", json={"action": "list_chats"})).status_code == 404


async def test_dashboard_page_served(tmp_path: Path) -> None:
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        resp = await client.get("/admin")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert resp.headers["cache-control"] == "no-store"
        body = resp.text
        # CSS and JS are inlined, not left as placeholders.
        assert "/* __CSS__ */" not in body
        assert "/* __JS__ */" not in body
        assert "LINE Connect Dashboard" in body


async def test_custom_admin_path(tmp_path: Path) -> None:
    settings = admin_settings(tmp_path, admin_path="/ops/console")
    async with running_app(settings) as app, asgi_client(app) as client:
        assert (await client.get("/ops/console")).status_code == 200
        assert (await client.get("/admin")).status_code == 404


# ── auth ───────────────────────────────────────────────────────────


async def test_login_and_token_auth(tmp_path: Path) -> None:
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        resp = await call(client, "login", password=ADMIN_PASSWORD)
        assert resp.status_code == 200
        token = resp.json()["token"]
        assert resp.json()["expires"] > ""

        assert (await call(client, "list_chats", token=token)).status_code == 200
        assert (await call(client, "list_chats")).status_code == 401
        assert (await call(client, "list_chats", token="bogus")).status_code == 401


async def test_password_is_not_accepted_as_token(tmp_path: Path) -> None:
    """Upstream fell back to the raw password on any action (line.py:127-130)."""
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        resp = await call(client, "list_chats", password=ADMIN_PASSWORD)
        assert resp.status_code == 401
        resp = await call(client, "list_chats", token=ADMIN_PASSWORD)
        assert resp.status_code == 401


async def test_lockout_after_failed_attempts(tmp_path: Path) -> None:
    settings = admin_settings(tmp_path, admin_login_max_attempts=3)
    async with running_app(settings) as app, asgi_client(app) as client:
        for _ in range(3):
            assert (await call(client, "login", password="wrong")).status_code == 401
        locked = await call(client, "login", password=ADMIN_PASSWORD)
        assert locked.status_code == 429
        assert locked.json()["error"] == "too_many_attempts"


async def test_successful_login_resets_counter(tmp_path: Path) -> None:
    settings = admin_settings(tmp_path, admin_login_max_attempts=3)
    async with running_app(settings) as app, asgi_client(app) as client:
        for _ in range(2):
            await call(client, "login", password="wrong")
        assert (await call(client, "login", password=ADMIN_PASSWORD)).status_code == 200
        for _ in range(2):
            assert (await call(client, "login", password="wrong")).status_code == 401
        # Still under the limit because the success cleared the tally.
        assert (await call(client, "login", password=ADMIN_PASSWORD)).status_code == 200


async def test_token_survives_restart(tmp_path: Path) -> None:
    settings = admin_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        token = await login(client)
    async with running_app(settings) as app, asgi_client(app) as client:
        assert (await call(client, "list_chats", token=token)).status_code == 200


async def test_unknown_action_is_400(tmp_path: Path) -> None:
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        token = await login(client)
        resp = await call(client, "toggle_bot", token=token, chat_id="user:U1")
        assert resp.status_code == 400
        assert "unknown action" in resp.json()["error"]


async def test_webhook_still_rejects_unsigned_requests(tmp_path: Path) -> None:
    """Mounting admin must not loosen the webhook."""
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        resp = await client.post(
            app.state.settings.webhook_path, json=webhook_payload(text_event())
        )
        assert resp.status_code == 400


# ── chat data ──────────────────────────────────────────────────────


@pytest.fixture
async def seeded(tmp_path: Path, mock_apis: Any) -> Any:
    """One chat with a user message and a bot reply already logged."""
    mock_apis.post(DIFY_CHAT_URL).mock(return_value=dify_stream_answer("Hi!", "c-1"))
    settings = admin_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await seed_chat(client, settings, app, text="hello there")
        yield app, client, await login(client)


async def test_list_chats_and_history(seeded: Any) -> None:
    _app, client, token = seeded

    chats = (await call(client, "list_chats", token=token)).json()["chats"]
    assert len(chats) == 1
    chat = chats[0]
    assert chat["id"] == "user:U1"
    assert chat["name"] == "Tim"
    assert chat["original_name"] == "Tim"
    assert chat["custom_name"] == ""
    assert chat["type"] == "user"
    assert chat["source_id"] == "U1"
    assert chat["last_message"] == "hello there"
    assert chat["mc"] == 2
    assert chat["starred"] is False
    assert chat["tags"] == []
    assert chat["disabled"] is False

    hist = (await call(client, "get_history", token=token, chat_id="user:U1")).json()
    assert hist["typing"] is False
    assert [(m["r"], m["t"]) for m in hist["history"]] == [
        ("user", "hello there"),
        ("bot", "Hi!"),
    ]
    assert hist["history"][0]["n"] == "Tim"
    assert hist["history"][0]["mid"] == "m-0001"
    assert "tp" not in hist["history"][0]  # text messages omit the type field


async def test_get_history_requires_chat_id(seeded: Any) -> None:
    _app, client, token = seeded
    resp = await call(client, "get_history", token=token)
    assert resp.status_code == 400


async def test_chat_meta_roundtrip(seeded: Any) -> None:
    _app, client, token = seeded

    empty = (await call(client, "get_chat_meta", token=token, chat_id="user:U1")).json()
    assert empty["meta"] == {
        "custom_name": "",
        "notes": "",
        "starred": False,
        "tags": [],
    }

    updated = (
        await call(
            client,
            "update_chat_meta",
            token=token,
            chat_id="user:U1",
            custom_name="VIP",
            tags=["vip", "urgent"],
            starred=True,
        )
    ).json()
    assert updated["ok"] is True
    assert updated["meta"] == {
        "custom_name": "VIP",
        "notes": "",
        "starred": True,
        "tags": ["vip", "urgent"],
    }

    # A partial update leaves untouched fields alone.
    await call(client, "update_chat_meta", token=token, chat_id="user:U1", notes="call")
    meta = (await call(client, "get_chat_meta", token=token, chat_id="user:U1")).json()
    assert meta["meta"]["notes"] == "call"
    assert meta["meta"]["custom_name"] == "VIP"

    chat = (await call(client, "list_chats", token=token)).json()["chats"][0]
    assert chat["name"] == "VIP"
    assert chat["original_name"] == "Tim"
    assert chat["starred"] is True
    assert chat["tags"] == ["vip", "urgent"]


async def test_typing_reflects_in_flight_job(tmp_path: Path, mock_apis: Any) -> None:
    """The indicator is derived from the inbox, with nothing written for it."""
    import asyncio

    release = asyncio.Event()

    async def blocking_handler(job: Any) -> None:
        await release.wait()

    settings = admin_settings(tmp_path)
    async with (
        running_app(settings, handler=blocking_handler) as app,
        asgi_client(app) as client,
    ):
        token = await login(client)
        app.state.repo.ensure_conversation("user:U1", "user", "U1", "Tim", "Tim")
        await post_signed(
            client, settings.webhook_path, webhook_payload(text_event())
        )
        for _ in range(100):  # wait for the worker to claim the job
            if app.state.repo.count_by_status().get("processing"):
                break
            await asyncio.sleep(0.01)

        during = await call(client, "get_history", token=token, chat_id="user:U1")
        assert during.json()["typing"] is True

        release.set()
        await app.state.pipeline.idle()
        after = await call(client, "get_history", token=token, chat_id="user:U1")
        assert after.json()["typing"] is False


# ── outbound / destructive / catalogues ────────────────────────────


async def test_send_message_pushes_and_logs(seeded: Any, mock_apis: Any) -> None:
    _app, client, token = seeded
    mock_apis.get("https://api.line.me/v2/bot/info", name="botinfo").mock(
        return_value=httpx.Response(200, json={"displayName": "Nani OA"})
    )
    await call(client, "update_chat_meta", token=token, chat_id="user:U1", custom_name="VIP")

    resp = await call(
        client,
        "send_message",
        token=token,
        chat_id="user:U1",
        text="Hi {username}, this is {account_name}",
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "sent_to": "U1"}

    push = mock_apis["push"]
    assert push.call_count == 1
    body = request_json(push, 0)
    assert body["to"] == "U1"
    assert body["messages"] == [
        {"type": "text", "text": "Hi VIP, this is Nani OA"}
    ]

    hist = (await call(client, "get_history", token=token, chat_id="user:U1")).json()
    assert hist["history"][-1]["r"] == "admin"
    assert hist["history"][-1]["t"] == "Hi VIP, this is Nani OA"
    # An operator reply must not re-mark the chat unread.
    chat = (await call(client, "list_chats", token=token)).json()["chats"][0]
    assert chat["last_message"] == "hello there"
    assert chat["mc"] == 3


async def test_send_message_validation(seeded: Any) -> None:
    _app, client, token = seeded
    assert (await call(client, "send_message", token=token, text="hi")).status_code == 400
    assert (
        await call(client, "send_message", token=token, chat_id="user:U1", text="  ")
    ).status_code == 400
    missing = await call(client, "send_message", token=token, chat_id="user:NOPE", text="hi")
    assert missing.status_code == 404


async def test_export_chat_is_the_whole_log(tmp_path: Path, mock_apis: Any) -> None:
    """Upstream exported whatever the browser had loaded — at most 100 rows."""
    settings = admin_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        token = await login(client)
        app.state.repo.ensure_conversation("user:U1", "user", "U1", "Tim", "Tim")
        for i in range(250):
            app.state.repo.log_message("user:U1", "user", f"msg {i}")

        resp = await call(client, "export_chat", token=token, chat_id="user:U1")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().splitlines()
        assert len(lines) == 251  # header + 250 rows
        assert "msg 0" in lines[1]
        assert "msg 249" in lines[-1]

        as_json = await call(
            client, "export_chat", token=token, chat_id="user:U1", format="json"
        )
        assert len(as_json.json()) == 250


async def test_export_chat_respects_row_cap(tmp_path: Path) -> None:
    settings = admin_settings(tmp_path, admin_export_max_rows=10)
    async with running_app(settings) as app, asgi_client(app) as client:
        token = await login(client)
        app.state.repo.ensure_conversation("user:U1", "user", "U1", "Tim", "Tim")
        for i in range(30):
            app.state.repo.log_message("user:U1", "user", f"m{i}")
        resp = await call(client, "export_chat", token=token, chat_id="user:U1")
        assert len(resp.text.strip().splitlines()) == 11


async def test_clear_history_keeps_cid_and_meta(seeded: Any) -> None:
    app, client, token = seeded
    app.state.repo.set_cid("user:U1", "c-1")
    await call(
        client, "update_chat_meta", token=token, chat_id="user:U1", notes="keep me"
    )

    assert (await call(client, "clear_history", token=token, chat_id="user:U1")).json() == {
        "ok": True
    }

    hist = (await call(client, "get_history", token=token, chat_id="user:U1")).json()
    assert hist["history"] == []
    assert app.state.repo.get_cid("user:U1") == "c-1"
    meta = (await call(client, "get_chat_meta", token=token, chat_id="user:U1")).json()
    assert meta["meta"]["notes"] == "keep me"
    # Cleared chats drop out of the inbox list but keep their conversation row.
    assert (await call(client, "list_chats", token=token)).json()["chats"] == []


async def test_clear_all_chats(seeded: Any) -> None:
    app, client, token = seeded
    app.state.repo.set_cid("user:U1", "c-1")
    resp = await call(client, "clear_all_chats", token=token)
    assert resp.json() == {"ok": True, "cleared": 1}
    assert (await call(client, "list_chats", token=token)).json()["chats"] == []
    assert app.state.repo.get_cid("user:U1") == "c-1"


async def test_manage_tags(seeded: Any) -> None:
    _app, client, token = seeded
    assert (await call(client, "manage_tags", token=token)).json() == {"tags": []}
    assert (await call(client, "manage_tags", token=token, op="add", tag="vip")).json()[
        "tags"
    ] == ["vip"]
    # Adding twice is a success, not a conflict.
    assert (await call(client, "manage_tags", token=token, op="add", tag="vip")).json()[
        "tags"
    ] == ["vip"]
    await call(client, "manage_tags", token=token, op="add", tag="urgent")

    await call(
        client, "update_chat_meta", token=token, chat_id="user:U1", tags=["vip", "urgent"]
    )
    await call(client, "manage_tags", token=token, op="rename", tag="vip", new_tag="gold")
    chat = (await call(client, "list_chats", token=token)).json()["chats"][0]
    assert chat["tags"] == ["gold", "urgent"]

    await call(client, "manage_tags", token=token, op="remove", tag="gold")
    assert (await call(client, "manage_tags", token=token)).json()["tags"] == ["urgent"]
    chat = (await call(client, "list_chats", token=token)).json()["chats"][0]
    assert chat["tags"] == ["urgent"]

    assert (await call(client, "manage_tags", token=token, op="add")).status_code == 400
    assert (await call(client, "manage_tags", token=token, op="bogus")).status_code == 400


async def test_manage_templates(seeded: Any) -> None:
    _app, client, token = seeded
    assert (await call(client, "manage_templates", token=token)).json() == {
        "templates": []
    }
    added = (
        await call(
            client, "manage_templates", token=token, op="add", title="Greet", body="Hello!"
        )
    ).json()["templates"]
    assert len(added) == 1
    template_id = added[0]["id"]
    assert added[0]["title"] == "Greet"

    edited = (
        await call(
            client,
            "manage_templates",
            token=token,
            op="edit",
            id=template_id,
            title="Greeting",
            body="Hi there!",
        )
    ).json()["templates"]
    assert edited[0]["title"] == "Greeting"
    assert edited[0]["body"] == "Hi there!"
    assert edited[0]["updated_at"] is not None

    assert (
        await call(client, "manage_templates", token=token, op="delete", id=template_id)
    ).json() == {"templates": []}

    assert (
        await call(client, "manage_templates", token=token, op="add", title="x")
    ).status_code == 400


async def test_non_string_token_is_rejected(tmp_path: Path) -> None:
    """A JSON body is attacker-shaped: token may be any type."""
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        for bogus in (123, None, {"a": 1}, ["x"], True):
            resp = await client.post(
                "/admin", json={"action": "list_chats", "token": bogus}
            )
            assert resp.status_code == 401, bogus


async def test_non_object_body_is_rejected(tmp_path: Path) -> None:
    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        assert (await client.post("/admin", json=["list_chats"])).status_code == 400
        assert (
            await client.post(
                "/admin", content=b"not json", headers={"Content-Type": "application/json"}
            )
        ).status_code == 400


async def test_handler_exception_becomes_500_not_a_traceback(tmp_path: Path) -> None:
    from line_connect.admin import actions as admin_actions

    async with (
        running_app(admin_settings(tmp_path)) as app,
        asgi_client(app) as client,
    ):
        token = await login(client)
        original = admin_actions.REGISTRY["list_chats"]

        async def boom(ctx: Any, body: Any) -> Any:
            raise RuntimeError("db on fire")

        admin_actions.REGISTRY["list_chats"] = admin_actions.Action(boom, True)
        try:
            resp = await call(client, "list_chats", token=token)
        finally:
            admin_actions.REGISTRY["list_chats"] = original
        assert resp.status_code == 500
        assert resp.json() == {"error": "internal error"}
        assert "db on fire" not in resp.text
