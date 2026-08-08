"""Media library end to end: an inbound image becomes a servable dashboard asset."""

from pathlib import Path
from typing import Any

import httpx

from .conftest import (
    DIFY_CHAT_URL,
    DIFY_UPLOAD_URL,
    asgi_client,
    dify_stream_answer,
    line_content_url,
    make_settings,
    media_event,
    post_signed,
    running_app,
    webhook_payload,
)
from .test_admin_api import ADMIN_PASSWORD, call, login

IMAGE_BYTES = b"\xff\xd8\xff-fake-jpeg"


def media_settings(tmp_path: Path, **overrides: Any) -> Any:
    defaults: dict[str, Any] = dict(
        admin_password=ADMIN_PASSWORD,
        media_support_enabled=True,
        media_store_enabled=True,
        media_dir=str(tmp_path / "media"),
    )
    defaults.update(overrides)
    return make_settings(tmp_path, **defaults)


def mock_image_apis(mock_apis: Any, msg_id: str = "m-media-1") -> None:
    mock_apis.get(line_content_url(msg_id)).mock(
        return_value=httpx.Response(
            200, content=IMAGE_BYTES, headers={"content-type": "image/jpeg"}
        )
    )
    mock_apis.post(DIFY_UPLOAD_URL).mock(return_value=httpx.Response(200, json={"id": "f1"}))
    mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer("Nice picture", "c-1")
    )


async def send_image(client: httpx.AsyncClient, app: Any, settings: Any) -> None:
    await post_signed(client, settings.webhook_path, webhook_payload(media_event()))
    await app.state.pipeline.idle()


async def test_image_is_stored_and_served(tmp_path: Path, mock_apis: Any) -> None:
    mock_image_apis(mock_apis)
    settings = media_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await send_image(client, app, settings)
        token = await login(client)

        hist = (await call(client, "get_history", token=token, chat_id="user:U1")).json()
        user_msg, bot_msg = hist["history"]
        assert user_msg["tp"] == "image"
        assert user_msg["mid"] == "m-media-1"
        # The bot's answer *about* an image is text, not an image. It is logged
        # with msg_type='image', so if the mapper passed that through the UI
        # would render "Sent an image" instead of what the AI actually said.
        assert bot_msg["r"] == "bot"
        assert bot_msg["t"] == "Nice picture"
        assert "tp" not in bot_msg

        resp = await call(client, "get_image", token=token, message_id="m-media-1")
        assert resp.status_code == 200
        assert resp.content == IMAGE_BYTES
        assert resp.headers["content-type"] == "image/jpeg"


async def test_image_survives_restart(tmp_path: Path, mock_apis: Any) -> None:
    """The bytes are on the PVC, not in memory."""
    mock_image_apis(mock_apis)
    settings = media_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await send_image(client, app, settings)
    async with running_app(settings) as app, asgi_client(app) as client:
        token = await login(client)
        resp = await call(client, "get_image", token=token, message_id="m-media-1")
        assert resp.content == IMAGE_BYTES


async def test_missing_image_is_404(tmp_path: Path, mock_apis: Any) -> None:
    settings = media_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        token = await login(client)
        assert (
            await call(client, "get_image", token=token, message_id="nope")
        ).status_code == 404
        assert (await call(client, "get_image", token=token)).status_code == 400


async def test_get_image_requires_auth(tmp_path: Path, mock_apis: Any) -> None:
    settings = media_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        assert (
            await client.post("/admin", json={"action": "get_image", "message_id": "m-1"})
        ).status_code == 401


async def test_nothing_stored_when_disabled(tmp_path: Path, mock_apis: Any) -> None:
    mock_image_apis(mock_apis)
    settings = media_settings(tmp_path, media_store_enabled=False)
    async with running_app(settings) as app, asgi_client(app) as client:
        await send_image(client, app, settings)
        token = await login(client)
        resp = await call(client, "get_image", token=token, message_id="m-media-1")
        assert resp.status_code == 404
        assert not (tmp_path / "media").exists()


async def test_clear_history_removes_media_files(tmp_path: Path, mock_apis: Any) -> None:
    mock_image_apis(mock_apis)
    settings = media_settings(tmp_path)
    async with running_app(settings) as app, asgi_client(app) as client:
        await send_image(client, app, settings)
        token = await login(client)
        assert list((tmp_path / "media").iterdir())

        await call(client, "clear_history", token=token, chat_id="user:U1")
        assert list((tmp_path / "media").iterdir()) == []
        assert (
            await call(client, "get_image", token=token, message_id="m-media-1")
        ).status_code == 404
