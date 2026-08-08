"""LINE Connect — FlexMessage reply formatting.

Ported line-for-line from upstream `_format_flex_reply`, `_md_to_flex_contents`,
`_flex_rich_text`, `_flex_list_item`, `_flex_table` (public names, underscores
dropped).

Bug fix (image URL whitelist, risk R5): only URLs passing
`is_valid_image_url` are turned into `image` messages; invalid ones are
dropped instead of being sent to LINE (which would fail the whole batch).

The 45000-byte bubble-size guard and the 400-char altText truncation are
preserved unchanged from upstream.
"""

import json
import re
from typing import Any

from line_connect.line.messages import LINE_MAX_MESSAGES, image_msg

from .markdown import is_valid_image_url, strip_markdown

_MAX_FLEX_BUBBLE_BYTES = 45000
_MAX_ALT_TEXT_LEN = 400
_HEADING_SIZES = {1: "xxl", 2: "xl", 3: "lg", 4: "md", 5: "sm", 6: "xs"}


def format_flex_reply(answer: str) -> list[dict[str, Any]] | None:
    """Convert a markdown answer to FlexMessage bubble + image messages."""
    messages: list[dict[str, Any]] = []
    image_urls = re.findall(r"!\[.*?\]\((https?://[^\s)]+)\)", answer)
    valid_image_urls = [url for url in image_urls if is_valid_image_url(url)]
    clean = re.sub(r"!\[.*?\]\(https?://[^\s)]+\)", "", answer).strip()

    if clean:
        contents = md_to_flex_contents(clean)
        if not contents:
            return None
        bubble = {
            "type": "bubble",
            "size": "giga",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "xl",
                "contents": contents,
            },
        }
        flex_json = json.dumps(bubble, ensure_ascii=False)
        if len(flex_json.encode("utf-8")) > _MAX_FLEX_BUBBLE_BYTES:
            return None  # Too large for FlexMessage, fall back to text
        messages.append(
            {
                "type": "flex",
                "altText": strip_markdown(clean)[:_MAX_ALT_TEXT_LEN],
                "contents": bubble,
            }
        )

    for url in valid_image_urls:
        if len(messages) >= LINE_MAX_MESSAGES:
            break
        messages.append(image_msg(url))

    return messages[:LINE_MAX_MESSAGES] if messages else None


def md_to_flex_contents(text: str) -> list[dict[str, Any]]:
    """Parse markdown text into FlexMessage body contents."""
    contents: list[dict[str, Any]] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            contents.append(
                flex_rich_text(m.group(2), size=_HEADING_SIZES.get(level, "md"), weight="bold")
            )
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            contents.append({"type": "separator", "margin": "lg"})
            i += 1
            continue

        # Bullet list
        m = re.match(r"^[-*+]\s+(.*)", stripped)
        if m:
            contents.append(flex_list_item("•", m.group(1)))
            i += 1
            continue

        # Numbered list
        m = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m:
            contents.append(flex_list_item(f"{m.group(1)}.", m.group(2)))
            i += 1
            continue

        # Table (header + separator + rows)
        if "|" in stripped and i + 1 < len(lines):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if re.match(r"^[|\s:-]+$", next_line) and "|" in next_line:
                table_lines: list[str] = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i].strip())
                    i += 1
                tbl = flex_table(table_lines)
                if tbl:
                    contents.append(tbl)
                continue

        # Blockquote
        m = re.match(r"^>\s*(.*)", stripped)
        if m:
            contents.append(
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "width": "3px",
                            "backgroundColor": "#06C755",
                            "contents": [{"type": "filler"}],
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "paddingStart": "md",
                            "contents": [flex_rich_text(m.group(1), color="#666666")],
                        },
                    ],
                }
            )
            i += 1
            continue

        # Regular paragraph
        contents.append(flex_rich_text(stripped))
        i += 1

    return contents


def flex_rich_text(
    text: str, size: str = "md", weight: str = "regular", color: str = "#333333"
) -> dict[str, Any]:
    """Create text component with inline bold, code, and link formatting."""
    if not re.search(r"\*\*.*?\*\*|`[^`]+`|\[.*?\]\(.*?\)", text):
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        return {
            "type": "text",
            "text": clean,
            "size": size,
            "weight": weight,
            "color": color,
            "wrap": True,
        }

    spans: list[dict[str, Any]] = []
    plain_parts: list[str] = []
    for part in re.split(r"(\*\*.*?\*\*|`[^`]+`|\[.*?\]\(.*?\))", text):
        if not part:
            continue
        m = re.match(r"^\*\*(.*?)\*\*$", part)
        if m:
            spans.append({"type": "span", "text": m.group(1), "weight": "bold", "color": color})
            plain_parts.append(m.group(1))
            continue
        m = re.match(r"^`([^`]+)`$", part)
        if m:
            spans.append(
                {"type": "span", "text": m.group(1), "color": "#E74C3C", "weight": "bold"}
            )
            plain_parts.append(m.group(1))
            continue
        m = re.match(r"^\[(.*?)\]\((.*?)\)$", part)
        if m:
            spans.append(
                {
                    "type": "span",
                    "text": m.group(1),
                    "color": "#06C755",
                    "decoration": "underline",
                }
            )
            plain_parts.append(m.group(1))
            continue
        spans.append({"type": "span", "text": part, "color": color})
        plain_parts.append(part)

    return {
        "type": "text",
        "text": "".join(plain_parts),
        "contents": spans,
        "size": size,
        "weight": weight,
        "wrap": True,
    }


def flex_list_item(marker: str, text: str) -> dict[str, Any]:
    """List item with marker bullet/number and rich text."""
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "margin": "sm",
        "contents": [
            {
                "type": "text",
                "text": marker,
                "size": "md",
                "color": "#06C755",
                "flex": 0,
                "weight": "bold",
            },
            flex_rich_text(text),
        ],
    }


def flex_table(lines: list[str]) -> dict[str, Any] | None:
    """Convert markdown table to FlexMessage grid."""
    if len(lines) < 3:
        return None

    def parse_row(line: str) -> list[str]:
        return [c.strip() for c in line.strip("|").split("|")]

    header = parse_row(lines[0])
    rows = [
        parse_row(ln)
        for ln in lines[2:]
        if ln.strip() and not re.match(r"^[|\s:-]+$", ln.strip())
    ]
    col_count = len(header)

    header_cells = [
        {
            "type": "text",
            "text": c or " ",
            "size": "xs",
            "weight": "bold",
            "color": "#FFFFFF",
            "flex": 1,
            "align": "center",
        }
        for c in header
    ]
    table_contents: list[dict[str, Any]] = [
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "backgroundColor": "#06C755",
            "paddingAll": "sm",
            "contents": header_cells,
        }
    ]

    for idx, row in enumerate(rows):
        bg = "#F8F8F8" if idx % 2 == 0 else "#FFFFFF"
        cells = [
            {
                "type": "text",
                "text": (row[j] if j < len(row) else "") or " ",
                "size": "xs",
                "color": "#333333",
                "flex": 1,
                "align": "center",
                "wrap": True,
            }
            for j in range(col_count)
        ]
        table_contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "backgroundColor": bg,
                "paddingAll": "sm",
                "contents": cells,
            }
        )

    return {
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "cornerRadius": "md",
        "borderWidth": "1px",
        "borderColor": "#E0E0E0",
        "contents": table_contents,
    }
