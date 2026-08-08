from line_connect.formatting.markdown import is_valid_image_url, split_text, strip_markdown


class TestStripMarkdown:
    def test_bold_double_star(self) -> None:
        assert strip_markdown("**bold**") == "bold"

    def test_bold_double_underscore(self) -> None:
        assert strip_markdown("__bold__") == "bold"

    def test_italic_single_star(self) -> None:
        assert strip_markdown("*italic*") == "italic"

    def test_italic_single_underscore(self) -> None:
        assert strip_markdown("_italic_") == "italic"

    def test_strikethrough(self) -> None:
        assert strip_markdown("~~strike~~") == "strike"

    def test_inline_code(self) -> None:
        assert strip_markdown("`code`") == "code"

    def test_fenced_code_block(self) -> None:
        # Upstream quirk, faithfully preserved: the inline-code regex runs
        # before the fenced-code regex, so it greedily consumes one backtick
        # off each end of the triple-backtick fence first. The fenced-code
        # regex then strips only the remaining two backticks per side down to
        # nothing extra, leaving "``" remnants rather than a clean strip.
        assert strip_markdown("```\nprint(1)\n```") == "``\nprint(1)\n``"

    def test_heading(self) -> None:
        assert strip_markdown("### Heading") == "Heading"

    def test_all_heading_levels_stripped(self) -> None:
        for level in range(1, 7):
            assert strip_markdown(f"{'#' * level} Title") == "Title"

    def test_link_becomes_text_and_url(self) -> None:
        assert (
            strip_markdown("[LINE](https://line.me)") == "LINE (https://line.me)"
        )

    def test_blockquote(self) -> None:
        assert strip_markdown("> quoted text") == "quoted text"

    def test_horizontal_rule(self) -> None:
        assert strip_markdown("---") == "─────"

    def test_excess_blank_lines_collapsed(self) -> None:
        assert strip_markdown("para1\n\n\n\npara2") == "para1\n\npara2"


class TestSplitText:
    def test_splits_at_newline_within_limit(self) -> None:
        text = ("a" * 10) + "\n" + ("b" * 10)
        assert split_text(text, 15) == ["a" * 10, "b" * 10]

    def test_hard_cut_when_no_newline(self) -> None:
        text = "x" * 25
        assert split_text(text, 10) == ["x" * 10, "x" * 10, "x" * 5]

    def test_length_exactly_at_limit_returns_single_chunk(self) -> None:
        text = "y" * 20
        assert split_text(text, 20) == [text]

    def test_far_exceeds_limit_produces_many_chunks(self) -> None:
        text = "a" * 30000
        chunks = split_text(text, 5000)
        assert len(chunks) == 6
        assert all(len(c) == 5000 for c in chunks)
        assert "".join(chunks) == text


class TestIsValidImageUrl:
    def test_valid_https_png(self) -> None:
        assert is_valid_image_url("https://x.test/a.png") is True

    def test_rejects_http(self) -> None:
        assert is_valid_image_url("http://x.test/a.png") is False

    def test_rejects_bad_extension(self) -> None:
        assert is_valid_image_url("https://x.test/a.svg") is False

    def test_rejects_missing_extension(self) -> None:
        assert is_valid_image_url("https://x.test/a") is False

    def test_rejects_over_length_limit(self) -> None:
        long_url = "https://x.test/" + ("a" * 2000) + ".png"
        assert is_valid_image_url(long_url) is False

    def test_query_string_ignored_for_extension_check(self) -> None:
        assert is_valid_image_url("https://x.test/a.png?size=large") is True

    def test_case_insensitive_extension(self) -> None:
        assert is_valid_image_url("https://x.test/a.PNG") is True
