from line_connect.line.events import LineSource
from line_connect.line.messages import (
    LINE_MAX_TEXT,
    chat_key_of,
    image_msg,
    push_target,
    text_msg,
)


class TestChatKey:
    def test_user(self) -> None:
        assert chat_key_of(LineSource(type="user", userId="U1")) == "user:U1"

    def test_group_wins_over_user(self) -> None:
        src = LineSource(type="group", groupId="G1", userId="U1")
        assert chat_key_of(src) == "group:G1"

    def test_room(self) -> None:
        assert chat_key_of(LineSource(type="room", roomId="R1", userId="U1")) == "room:R1"

    def test_missing_user_id(self) -> None:
        assert chat_key_of(LineSource(type="user")) == "user:unknown"


class TestPushTarget:
    def test_group_target(self) -> None:
        assert push_target(LineSource(type="group", groupId="G1", userId="U1")) == "G1"

    def test_user_target(self) -> None:
        assert push_target(LineSource(type="user", userId="U1")) == "U1"


class TestTextMsg:
    def test_short_text_untouched(self) -> None:
        assert text_msg("hi") == {"type": "text", "text": "hi"}

    def test_exactly_at_limit(self) -> None:
        text = "x" * LINE_MAX_TEXT
        assert text_msg(text)["text"] == text

    def test_over_limit_truncated_with_ellipsis(self) -> None:
        result = text_msg("x" * (LINE_MAX_TEXT + 1))["text"]
        assert len(result) == LINE_MAX_TEXT
        assert result.endswith("\n...")


def test_image_msg_shape() -> None:
    assert image_msg("https://x.test/a.png") == {
        "type": "image",
        "originalContentUrl": "https://x.test/a.png",
        "previewImageUrl": "https://x.test/a.png",
    }
