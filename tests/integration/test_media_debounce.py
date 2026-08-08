"""Media pipeline: debounce batching, kind separation, size caps (§7.5)."""

import asyncio
import itertools
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
    request_json,
    running_app,
    webhook_payload,
)


def mock_upload(mock_apis: Any) -> Any:
    counter = itertools.count(1)
    return mock_apis.post(DIFY_UPLOAD_URL, name="upload").mock(
        side_effect=lambda request: httpx.Response(
            200, json={"id": f"file-{next(counter)}"}
        )
    )


def mock_content(mock_apis: Any, msg_id: str, body: bytes = b"BYTES") -> None:
    mock_apis.get(line_content_url(msg_id)).mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "image/jpeg"}
        )
    )


async def test_three_images_batched_into_one_dify_call(
    tmp_path: Path, mock_apis: Any
) -> None:
    upload_route = mock_upload(mock_apis)
    for i in (1, 2, 3):
        mock_content(mock_apis, f"m-img-{i}")
    dify_route = mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer("Three nice pics!", "c-img")
    )
    settings = make_settings(
        tmp_path,
        media_support_enabled=True,
        media_debounce_seconds=0.05,
        multi_image_prompt_template="User sent {count} images",
    )
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(
                *(
                    media_event(
                        msg_id=f"m-img-{i}",
                        event_id=f"evt-img-{i}",
                        reply_token=f"rt-img-{i}",
                    )
                    for i in (1, 2, 3)
                )
            ),
        )
        await app.state.pipeline.idle()  # three uploads buffered
        await asyncio.sleep(0.2)  # debounce window closes, flush enqueued
        await app.state.pipeline.idle()

    assert upload_route.call_count == 3
    assert dify_route.call_count == 1, "one Dify call for the whole batch"
    body = request_json(dify_route, 0)
    assert body["query"] == "User sent 3 images"
    files = body["inputs"]["img"]
    assert [f["upload_file_id"] for f in files] == ["file-1", "file-2", "file-3"]
    assert all(f["type"] == "image" for f in files)
    deliveries = mock_apis["reply"].call_count + mock_apis["push"].call_count
    assert deliveries == 1, "exactly one answer for three images"


async def test_image_and_pdf_flush_separately(tmp_path: Path, mock_apis: Any) -> None:
    """Upstream shared one debounce key across kinds — a PDF polluted the image
    batch. Kinds must produce two independent Dify calls with their own vars."""
    mock_upload(mock_apis)
    mock_content(mock_apis, "m-img-1")
    mock_content(mock_apis, "m-pdf-1", body=b"%PDF-1.4")
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    dify_route.side_effect = [
        dify_stream_answer("about the image", "c-m"),
        dify_stream_answer("about the pdf", "c-m"),
    ]
    settings = make_settings(
        tmp_path, media_support_enabled=True, media_debounce_seconds=0.05
    )
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(
                media_event(msg_id="m-img-1", event_id="evt-mix-1", reply_token="rt-x1"),
                media_event(
                    msg_type="file",
                    msg_id="m-pdf-1",
                    event_id="evt-mix-2",
                    reply_token="rt-x2",
                    file_name="doc.pdf",
                ),
            ),
        )
        await app.state.pipeline.idle()
        await asyncio.sleep(0.2)
        await app.state.pipeline.idle()

    assert dify_route.call_count == 2, "image and file batches must not merge"
    bodies = [request_json(dify_route, i) for i in range(2)]
    image_bodies = [b for b in bodies if "img" in b["inputs"]]
    file_bodies = [b for b in bodies if "files" in b["inputs"]]
    assert len(image_bodies) == 1 and len(file_bodies) == 1
    assert image_bodies[0]["inputs"]["img"][0]["type"] == "image"
    assert file_bodies[0]["inputs"]["files"][0]["type"] == "document"


async def test_single_image_uses_user_image_prompt(tmp_path: Path, mock_apis: Any) -> None:
    """Regression: upstream overwrote the configured image_prompt with a
    hardcoded Thai string. Single image → the user's prompt verbatim."""
    mock_upload(mock_apis)
    mock_content(mock_apis, "m-img-solo")
    dify_route = mock_apis.post(DIFY_CHAT_URL).mock(
        return_value=dify_stream_answer("a cat", "c-1")
    )
    settings = make_settings(
        tmp_path,
        media_support_enabled=True,
        media_debounce_seconds=0,  # immediate path
        image_prompt="請描述這張圖片",
    )
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(media_event(msg_id="m-img-solo", event_id="evt-solo")),
        )
        await app.state.pipeline.idle()

    assert dify_route.call_count == 1
    assert request_json(dify_route, 0)["query"] == "請描述這張圖片"


async def test_oversize_download_is_dropped(tmp_path: Path, mock_apis: Any) -> None:
    upload_route = mock_upload(mock_apis)
    mock_apis.get(line_content_url("m-big")).mock(
        return_value=httpx.Response(
            200,
            content=b"x" * (2 * 1024 * 1024),
            headers={"content-type": "image/jpeg"},
        )
    )
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    settings = make_settings(
        tmp_path, media_support_enabled=True, media_max_download_mb=1
    )
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(media_event(msg_id="m-big", event_id="evt-big")),
        )
        await app.state.pipeline.idle()
        assert app.state.repo.count_by_status() == {"done": 1}

    assert upload_route.call_count == 0, "oversize file must never reach Dify"
    assert dify_route.call_count == 0


async def test_media_disabled_image_gets_notice(tmp_path: Path, mock_apis: Any) -> None:
    dify_route = mock_apis.post(DIFY_CHAT_URL)
    settings = make_settings(tmp_path, media_support_enabled=False)
    async with running_app(settings) as app, asgi_client(app) as client:
        await post_signed(
            client,
            settings.webhook_path,
            webhook_payload(media_event(msg_id="m-no", event_id="evt-no")),
        )
        await app.state.pipeline.idle()

    assert dify_route.call_count == 0
    reply_route = mock_apis["reply"]
    assert reply_route.call_count == 1
    assert "not supported" in request_json(reply_route, 0)["messages"][0]["text"]