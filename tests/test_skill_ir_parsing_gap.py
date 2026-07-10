"""Direct unit coverage for app.adapters.skill_ir markdown-section parsers
that previously had no dedicated tests: _parse_purpose_block, _parse_bullet_list,
and _parse_examples. These feed the Skill export IR directly from user-authored
markdown — malformed or empty sections must degrade gracefully rather than
producing garbled exports.
"""

from app.adapters.skill_ir import (
    SkillExample,
    _parse_bullet_list,
    _parse_examples,
    _parse_purpose_block,
)


class TestParsePurposeBlock:
    def test_empty_text_returns_empty_tuple(self) -> None:
        assert _parse_purpose_block("") == ("", "")

    def test_legacy_single_block_is_kept_as_purpose(self) -> None:
        purpose, when = _parse_purpose_block("Summarizes long documents into bullets.")
        assert purpose == "Summarizes long documents into bullets."
        assert when == ""

    def test_what_and_when_labels_are_split(self) -> None:
        text = "**What:** Summarizes text.\n**When to use:** Long documents."
        purpose, when = _parse_purpose_block(text)
        assert purpose == "Summarizes text."
        assert when == "Long documents."

    def test_multiline_what_block_is_joined(self) -> None:
        text = "**What:** Summarizes text\nacross multiple lines."
        purpose, when = _parse_purpose_block(text)
        assert purpose == "Summarizes text across multiple lines."
        assert when == ""

    def test_only_when_label_leaves_purpose_empty(self) -> None:
        text = "**When to use:** For long documents."
        purpose, when = _parse_purpose_block(text)
        assert purpose == ""
        assert when == "For long documents."

    def test_strips_markdown_code_fence(self) -> None:
        text = "```\n**What:** Fenced purpose.\n```"
        purpose, when = _parse_purpose_block(text)
        assert purpose == "Fenced purpose."


class TestParseBulletList:
    def test_no_bullets_returns_empty(self) -> None:
        assert _parse_bullet_list("Just a plain sentence.") == []

    def test_dash_bullets(self) -> None:
        text = "- first\n- second\n- third"
        assert _parse_bullet_list(text) == ["first", "second", "third"]

    def test_star_bullets(self) -> None:
        text = "* alpha\n* beta"
        assert _parse_bullet_list(text) == ["alpha", "beta"]

    def test_mixed_bullet_markers(self) -> None:
        text = "- one\n* two"
        assert _parse_bullet_list(text) == ["one", "two"]

    def test_non_bullet_lines_are_skipped(self) -> None:
        text = "Intro line\n- real bullet\nanother stray line"
        assert _parse_bullet_list(text) == ["real bullet"]

    def test_empty_bullet_is_skipped(self) -> None:
        text = "- \n- content"
        assert _parse_bullet_list(text) == ["content"]


class TestParseExamples:
    def test_no_examples_returns_empty(self) -> None:
        assert _parse_examples("Nothing to see here.") == []

    def test_arrow_form_is_parsed(self) -> None:
        text = "Input: hello → Output: world"
        examples = _parse_examples(text)
        assert examples == [SkillExample(input="hello", output="world")]

    def test_ascii_arrow_form_is_parsed(self) -> None:
        text = "Input: 2+2 -> Output: 4"
        examples = _parse_examples(text)
        assert examples == [SkillExample(input="2+2", output="4")]

    def test_bulleted_example_strips_marker(self) -> None:
        text = "- Input: `foo` → Output: `bar`"
        examples = _parse_examples(text)
        assert examples == [SkillExample(input="foo", output="bar")]

    def test_multiple_examples_are_all_collected(self) -> None:
        text = "Input: a → Output: 1\nInput: b → Output: 2"
        examples = _parse_examples(text)
        assert examples == [
            SkillExample(input="a", output="1"),
            SkillExample(input="b", output="2"),
        ]

    def test_malformed_line_without_output_is_skipped(self) -> None:
        text = "Input: only input, no output marker"
        assert _parse_examples(text) == []
