"""Unit tests for app.token_optimizer's internal markdown-compaction pass.

_optimize_once and _optimize_markdown_text are only exercised indirectly today
through optimize_text() in test_token_optimizer.py, so their level-dependent
branches (blank-line collapsing, duplicate-line removal, list-marker
de-indentation) aren't pinned in isolation.
"""

from __future__ import annotations

from app.token_optimizer import _optimize_markdown_text, _optimize_once


class TestOptimizeMarkdownTextLevel1:
    def test_collapses_consecutive_blank_lines_into_one(self):
        text = "line one\n\n\n\nline two"
        assert _optimize_markdown_text(text, level=1) == "line one\n\nline two"

    def test_trims_trailing_whitespace_on_each_line(self):
        text = "line one   \nline two\t"
        assert _optimize_markdown_text(text, level=1) == "line one\nline two"

    def test_collapses_internal_runs_of_spaces(self):
        text = "a    b   c"
        assert _optimize_markdown_text(text, level=1) == "a b c"

    def test_collapses_internal_runs_of_tabs(self):
        text = "a\t\tb"
        assert _optimize_markdown_text(text, level=1) == "a b"

    def test_removes_exact_duplicate_consecutive_lines(self):
        text = "repeat me\nrepeat me\nkeep me"
        assert _optimize_markdown_text(text, level=1) == "repeat me\nkeep me"

    def test_does_not_dedupe_duplicate_blank_lines(self):
        # Blank-line collapsing is handled by the separate is_blank branch,
        # not the duplicate-consecutive-line check (which skips blanks).
        text = "a\n\n\nb"
        assert _optimize_markdown_text(text, level=1) == "a\n\nb"

    def test_preserves_single_blank_line_between_paragraphs(self):
        text = "para one\n\npara two"
        assert _optimize_markdown_text(text, level=1) == "para one\n\npara two"


class TestOptimizeMarkdownTextLevel2:
    def test_removes_all_blank_lines(self):
        text = "line one\n\n\nline two\n\nline three"
        assert _optimize_markdown_text(text, level=2) == "line one\nline two\nline three"

    def test_still_collapses_spaces_and_dedupes_lines(self):
        text = "a   b\na   b\n\nc"
        assert _optimize_markdown_text(text, level=2) == "a b\nc"


class TestOptimizeMarkdownTextLevel3:
    def test_strips_indentation_before_list_markers(self):
        # Indentation of 4+ spaces is treated as an indented code block and left
        # untouched (see TestOptimizeMarkdownTextPreservesStructure), so this only
        # exercises the 1-3 space case that _LIST_RE de-indents at level 3.
        text = "  - item one\n   * item two"
        assert _optimize_markdown_text(text, level=3) == "- item one\n* item two"

    def test_normalizes_internal_spacing_within_list_item_text(self):
        text = "- item  with   many    spaces"
        assert _optimize_markdown_text(text, level=1) == "- item with many spaces"


class TestOptimizeMarkdownTextPreservesStructure:
    def test_leaves_four_space_indented_code_content_untouched(self):
        # Trailing whitespace is still trimmed (every line is rstripped before
        # the indented-code passthrough check), but internal spacing and the
        # leading indentation itself are preserved verbatim.
        text = "    def  foo():   \n        pass   "
        result = _optimize_markdown_text(text, level=3)
        assert result == "    def  foo():\n        pass"

    def test_leaves_tab_indented_code_content_untouched(self):
        text = "\tvalue   =   1   "
        assert _optimize_markdown_text(text, level=1) == "\tvalue   =   1"

    def test_leaves_table_rows_untouched(self):
        text = "| a   | b |\n| --- | - |"
        assert _optimize_markdown_text(text, level=3) == "| a   | b |\n| --- | - |"


class TestOptimizeOnce:
    def test_preserves_fenced_code_block_verbatim(self):
        text = "Intro line\n\n\n```python\ndef  foo():\n    pass\n```\n\nOutro   line"
        result = _optimize_once(text, level=1)
        assert "def  foo():\n    pass" in result

    def test_optimizes_text_outside_fences(self):
        text = "a    b\n\n\n```\ncode   stays\n```"
        result = _optimize_once(text, level=1)
        assert result.startswith("a b\n")
        assert "code   stays" in result

    def test_normalizes_crlf_to_lf(self):
        text = "line one\r\nline two"
        result = _optimize_once(text, level=1)
        assert "\r" not in result

    def test_inserts_missing_newline_before_glued_fence(self):
        text = "Intro```python\nx = 1\n```"
        result = _optimize_once(text, level=1)
        assert "Intro\n```python" in result
