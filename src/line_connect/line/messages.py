"""Pure helpers: chat identity and LINE message construction."""

from typing import Any

from line_connect.line.events import LineSource

LINE_MAX_TEXT = 5000
LINE_MAX_MESSAGES = 5


def chat_key_of(source: LineSource) -> str:
    """One chat = one Dify conversation. Groups/rooms share a conversation,
    matching upstream semantics; the key is human-readable for debugging."""
    if source.group_id:
        return f"group:{source.group_id}"
    if source.room_id:
        return f"room:{source.room_id}"
    return f"user:{source.user_id or 'unknown'}"


def push_target(source: LineSource) -> str:
    """The `to` id for the Push API."""
    if source.group_id:
        return source.group_id
    if source.room_id:
        return source.room_id
    return source.user_id or ""


def text_msg(text: str) -> dict[str, Any]:
    if len(text) > LINE_MAX_TEXT:
        text = text[: LINE_MAX_TEXT - 4] + "\n..."
    return {"type": "text", "text": text}


def image_msg(url: str) -> dict[str, Any]:
    return {"type": "image", "originalContentUrl": url, "previewImageUrl": url}
