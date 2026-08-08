"""LINE Connect — markdown text utilities shared by plain-text and
FlexMessage reply formatting.

`strip_markdown` and `split_text` are ported line-for-line from upstream
`_strip_markdown` / `_split_text` (public names, underscore dropped).

`is_valid_image_url` is new — not present upstream. It whitelists image
URLs pulled out of an LLM-generated answer so a malformed URL never causes
LINE to reject the entire outgoing message batch (risk R5).
"""

import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

_VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_MAX_IMAGE_URL_LENGTH = 2000


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).strip("`").strip(), text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "─────", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def split_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut <= 0:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def is_valid_image_url(url: str) -> bool:
    """Whitelist an image URL: https scheme, length <= 2000, and a known
    image extension on the path (query string ignored)."""
    if len(url) > _MAX_IMAGE_URL_LENGTH:
        return False
    parts = urlsplit(url)
    if parts.scheme != "https":
        return False
    suffix = PurePosixPath(parts.path).suffix.lower()
    return suffix in _VALID_IMAGE_EXTENSIONS
