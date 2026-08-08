from line_connect.formatting.flex import (
    flex_list_item,
    flex_rich_text,
    flex_table,
    format_flex_reply,
    md_to_flex_contents,
)


class TestHeadings:
    def test_all_six_levels_map_to_expected_sizes(self) -> None:
        sizes = {1: "xxl", 2: "xl", 3: "lg", 4: "md", 5: "sm", 6: "xs"}
        for level, size in sizes.items():
            md = f"{'#' * level} Title{level}"
            contents = md_to_flex_contents(md)
            assert contents == [flex_rich_text(f"Title{level}", size=size, weight="bold")]


class TestLists:
    def test_bullet_list(self) -> None:
        contents = md_to_flex_contents("- item1\n- item2")
        assert contents == [
            flex_list_item("•", "item1"),
            flex_list_item("•", "item2"),
        ]

    def test_numbered_list(self) -> None:
        contents = md_to_flex_contents("1. first\n2. second")
        assert contents == [
            flex_list_item("1.", "first"),
            flex_list_item("2.", "second"),
        ]


class TestTable:
    def test_missing_trailing_column_padded_with_space(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 |"
        contents = md_to_flex_contents(md)
        assert len(contents) == 1
        table = contents[0]
        assert table is not None
        row_boxes = table["contents"][1:]  # [0] is the header row
        second_data_row = row_boxes[1]["contents"]
        assert second_data_row[0]["text"] == "3"
        assert second_data_row[1]["text"] == " "  # padded empty cell

    def test_flex_table_directly_too_few_lines_returns_none(self) -> None:
        assert flex_table(["| A |", "|---|"]) is None


class TestBlockquote:
    def test_blockquote_structure(self) -> None:
        contents = md_to_flex_contents("> Some quote")
        assert contents == [
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
                        "contents": [flex_rich_text("Some quote", color="#666666")],
                    },
                ],
            }
        ]


class TestHorizontalRule:
    def test_hr_becomes_separator(self) -> None:
        assert md_to_flex_contents("---") == [{"type": "separator", "margin": "lg"}]

    def test_hr_alternate_markers(self) -> None:
        assert md_to_flex_contents("***") == [{"type": "separator", "margin": "lg"}]
        assert md_to_flex_contents("___") == [{"type": "separator", "margin": "lg"}]


class TestInlineSpans:
    def test_plain_text_no_spans(self) -> None:
        result = flex_rich_text("Hello")
        assert result == {
            "type": "text",
            "text": "Hello",
            "size": "md",
            "weight": "regular",
            "color": "#333333",
            "wrap": True,
        }
        assert "contents" not in result

    def test_mixed_bold_code_link(self) -> None:
        text = "Hi **bold** and `code` and [link](https://x.test)"
        result = flex_rich_text(text)
        assert result["text"] == "Hi bold and code and link"
        spans = result["contents"]
        bold_span = next(s for s in spans if s["text"] == "bold")
        assert bold_span["weight"] == "bold"
        code_span = next(s for s in spans if s["text"] == "code")
        assert code_span["color"] == "#E74C3C"
        link_span = next(s for s in spans if s["text"] == "link")
        assert link_span["decoration"] == "underline"


class TestFlexBubbleSizeLimit:
    def test_bubble_over_45000_bytes_returns_none(self) -> None:
        big = "\n\n".join(f"paragraph {i} " + "x" * 80 for i in range(600))
        assert format_flex_reply(big) is None

    def test_alt_text_truncated_to_400_chars(self) -> None:
        answer = "A" * 1000
        result = format_flex_reply(answer)
        assert result is not None
        alt_text = result[0]["altText"]
        assert len(alt_text) == 400
        assert alt_text == "A" * 400


class TestInvalidImageUrlDropped:
    def test_invalid_image_url_produces_no_image_message(self) -> None:
        answer = "Some text\n\n![bad](http://x.test/a.png)"
        result = format_flex_reply(answer)
        assert result is not None
        assert all(msg["type"] != "image" for msg in result)

    def test_valid_image_url_still_produces_image_message(self) -> None:
        answer = "Some text\n\n![good](https://x.test/a.png)"
        result = format_flex_reply(answer)
        assert result is not None
        assert any(
            msg["type"] == "image" and msg["originalContentUrl"] == "https://x.test/a.png"
            for msg in result
        )
