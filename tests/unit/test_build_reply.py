"""build_reply dispatch: flex vs plain vs fallback."""

from typing import Any

from line_connect.formatting import build_reply


def test_flex_disabled_returns_plain_text() -> None:
    assert build_reply("hello", flex_enabled=False, strip_md=True) == [
        {"type": "text", "text": "hello"}
    ]


def test_flex_enabled_produces_flex_message() -> None:
    msgs = build_reply("# Title\n\nSome **bold** text", flex_enabled=True, strip_md=False)
    assert msgs[0]["type"] == "flex"
    assert msgs[0]["altText"]


def test_flex_oversize_falls_back_to_plain() -> None:
    huge = "word " * 12000  # far beyond the 45000-byte flex bubble cap
    msgs: list[dict[str, Any]] = build_reply(huge, flex_enabled=True, strip_md=True)
    assert all(m["type"] == "text" for m in msgs)


def test_flex_crash_falls_back_to_plain(monkeypatch: Any) -> None:
    import line_connect.formatting as fmt

    def boom(answer: str) -> None:
        raise RuntimeError("flex exploded")

    monkeypatch.setattr(fmt, "format_flex_reply", boom)
    msgs = build_reply("hello", flex_enabled=True, strip_md=True)
    assert msgs == [{"type": "text", "text": "hello"}]
