"""LINE Connect — plain-text reply formatting.

Ported from upstream `_format_reply` (public name, underscore dropped),
with two fixes over the upstream behaviour:

- Bug fix (image URL whitelist, risk R5): markdown image URLs are checked
  against `is_valid_image_url` before being turned into `image` messages.
  Invalid URLs are left in place as plain text instead of being dropped
  silently or sent to LINE as a broken image message (which would fail the
  whole batch).
- Bug fix (silent truncation): upstream's `messages[:LINE_MAX_MESSAGES]`
  silently drops any message beyond the 5-message LINE limit. Here the
  last kept message is annotated with a truncation notice instead.
"""

import re
from typing import Any

from line_connect.line.messages import LINE_MAX_MESSAGES, LINE_MAX_TEXT, image_msg, text_msg

from .markdown import is_valid_image_url, split_text, strip_markdown

_IMAGE_MD_RE = re.compile(r"!\[.*?\]\((https?://[^\s)]+)\)")
_TRUNCATION_SUFFIX = "\n…(message truncated)"
_TRUNCATION_STANDALONE = "…(message truncated)"


def format_plain_reply(answer: str, strip_md: bool) -> list[dict[str, Any]]:
    """Build plain-text LINE reply messages from a (possibly markdown) answer."""
    messages: list[dict[str, Any]] = []
    all_image_urls = _IMAGE_MD_RE.findall(answer)
    valid_image_urls = [url for url in all_image_urls if is_valid_image_url(url)]
    valid_set = set(valid_image_urls)

    def _strip_valid_images(match: re.Match[str]) -> str:
        return "" if match.group(1) in valid_set else match.group(0)

    clean = _IMAGE_MD_RE.sub(_strip_valid_images, answer)
    if strip_md:
        clean = strip_markdown(clean)
    clean = clean.strip()
    if clean:
        for chunk in split_text(clean, LINE_MAX_TEXT):
            messages.append(text_msg(chunk))
    for url in valid_image_urls:
        if len(messages) >= LINE_MAX_MESSAGES:
            break
        messages.append(image_msg(url))
    if not messages:
        messages = [text_msg(answer[:LINE_MAX_TEXT])]
    return _truncate_with_notice(messages)


def _truncate_with_notice(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cap at LINE_MAX_MESSAGES. Unlike upstream's plain slice, the last kept
    message carries a truncation notice instead of silently dropping the rest."""
    if len(messages) <= LINE_MAX_MESSAGES:
        return messages
    kept = messages[:LINE_MAX_MESSAGES]
    last = kept[-1]
    if last.get("type") == "text":
        text = str(last["text"])
        budget = LINE_MAX_TEXT - len(_TRUNCATION_SUFFIX)
        kept[-1] = text_msg(text[:budget] + _TRUNCATION_SUFFIX)
    else:
        kept[-1] = text_msg(_TRUNCATION_STANDALONE)
    return kept
