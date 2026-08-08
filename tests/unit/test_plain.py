from typing import Any

from line_connect.formatting.plain import _truncate_with_notice, format_plain_reply
from line_connect.line.messages import LINE_MAX_TEXT, image_msg, text_msg


class TestFormatPlainReply:
    def test_markdown_image_extracted_to_image_message(self) -> None:
        result = format_plain_reply("See this: ![pic](https://x.test/a.png)", True)
        assert result == [
            text_msg("See this:"),
            image_msg("https://x.test/a.png"),
        ]

    def test_empty_answer_falls_back_to_raw_text_msg(self) -> None:
        # Upstream `_format_reply` falls back to `_text_msg(answer[:LINE_MAX_TEXT])`
        # on the *raw* answer when no text/image messages were produced -- not a
        # friendly "couldn't generate a response" message. Preserved as-is.
        assert format_plain_reply("", True) == [text_msg("")]

    def test_whitespace_only_answer_falls_back_to_raw_text_msg(self) -> None:
        assert format_plain_reply("   ", True) == [text_msg("   ")]

    def test_invalid_image_url_http_scheme_dropped(self) -> None:
        answer = "![p](http://x.test/a.png)"
        result = format_plain_reply(answer, False)
        assert result == [text_msg(answer)]
        assert all(msg["type"] != "image" for msg in result)

    def test_invalid_image_url_bad_extension_dropped(self) -> None:
        answer = "![p](https://x.test/a.svg)"
        result = format_plain_reply(answer, False)
        assert result == [text_msg(answer)]
        assert all(msg["type"] != "image" for msg in result)

    def test_invalid_image_url_too_long_dropped(self) -> None:
        url = "https://x.test/" + ("a" * 2000) + ".png"
        answer = f"![p]({url})"
        result = format_plain_reply(answer, False)
        assert result == [text_msg(answer)]
        assert all(msg["type"] != "image" for msg in result)

    def test_valid_and_invalid_image_urls_mixed(self) -> None:
        answer = "![good](https://x.test/a.png) ![bad](http://x.test/b.png)"
        result = format_plain_reply(answer, False)
        image_messages = [m for m in result if m["type"] == "image"]
        assert image_messages == [image_msg("https://x.test/a.png")]
        # the invalid one survives as plain text somewhere in the reply
        assert any("http://x.test/b.png" in str(m.get("text", "")) for m in result)

    def test_over_5_messages_truncates_with_notice_on_text(self) -> None:
        # A long, unbroken answer forces split_text to hard-cut into exactly
        # 6 chunks of 5000 chars each (30000 / 5000), triggering the >5
        # message overflow purely via text chunking (see docstring on
        # `_truncate_with_notice` for why images can't cause this path).
        answer = "a" * 30000
        result = format_plain_reply(answer, False)
        assert len(result) == 5
        for msg in result[:4]:
            assert msg == text_msg("a" * 5000)
        last_text = result[-1]["text"]
        assert len(last_text) == LINE_MAX_TEXT
        assert last_text.endswith("…(message truncated)")
        assert last_text.startswith("a")


class TestTruncateWithNotice:
    def test_no_op_when_within_limit(self) -> None:
        messages: list[dict[str, Any]] = [text_msg("hi")]
        assert _truncate_with_notice(messages) == messages

    def test_non_text_last_message_replaced_with_notice(self) -> None:
        # This branch is unreachable via `format_plain_reply` itself (its own
        # image-appending loop is self-limiting to LINE_MAX_MESSAGES), but the
        # helper must still handle it correctly per spec for any future caller.
        messages: list[dict[str, Any]] = [image_msg(f"https://x.test/{i}.png") for i in range(6)]
        result = _truncate_with_notice(messages)
        assert len(result) == 5
        assert result[:4] == messages[:4]
        assert result[-1] == text_msg("…(message truncated)")
