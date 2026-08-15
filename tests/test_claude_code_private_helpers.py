"""
Coverage for small, pure, string-shaping helpers that were not directly
exercised by any existing test:

  * app/adapters/claude_code.py — _to_python_identifier, _strip_markdown_fences,
    _escape_triple_quotes
  * app/adapters/agent_ir.py    — _map_sections
  * app/adapters/agent_packs.py — _preview_order

Note: app/adapters/agent_packs.py's `_classify_kind` is intentionally NOT
re-tested here — it already has a dedicated, exhaustive test class
(`TestClassifyKind`) in tests/test_agent_packs_private_helpers.py.
"""

from __future__ import annotations

from app.adapters.agent_ir import _map_sections
from app.adapters.agent_packs import _preview_order
from app.adapters.claude_code import (
    _escape_triple_quotes,
    _strip_markdown_fences,
    _to_python_identifier,
)


# ---------------------------------------------------------------------------
# _to_python_identifier (claude_code.py's standalone copy)
# ---------------------------------------------------------------------------


class TestToPythonIdentifier:
    def test_simple_lowercase_name_is_unchanged(self):
        assert _to_python_identifier("weather") == "weather"

    def test_spaces_and_punctuation_become_single_underscores(self):
        assert _to_python_identifier("My Skill! Name") == "my_skill_name"

    def test_leading_digit_gets_skill_prefix(self):
        assert _to_python_identifier("123abc") == "skill_123abc"

    def test_python_keyword_collision_gets_skill_suffix(self):
        assert _to_python_identifier("class") == "class_skill"
        assert _to_python_identifier("import") == "import_skill"

    def test_empty_string_falls_back_to_skill(self):
        assert _to_python_identifier("") == "skill"

    def test_all_symbols_falls_back_to_skill(self):
        assert _to_python_identifier("!!!") == "skill"

    def test_collapses_repeated_underscores(self):
        assert _to_python_identifier("a__b___c") == "a_b_c"

    def test_uppercase_is_lowercased(self):
        assert _to_python_identifier("GetWeather") == "getweather"

    def test_strips_leading_and_trailing_symbols(self):
        assert _to_python_identifier("__hello__") == "hello"

    def test_leading_digit_and_keyword_do_not_both_apply(self):
        # "123" alone has no keyword collision after the skill_ prefix is applied.
        assert _to_python_identifier("123") == "skill_123"


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------


class TestStripMarkdownFences:
    def test_no_fence_returns_stripped_text_unchanged(self):
        assert _strip_markdown_fences("plain text") == "plain text"
        assert _strip_markdown_fences("  plain text  ") == "plain text"

    def test_strips_fence_with_language_tag(self):
        text = "```python\nprint('hi')\n```"
        assert _strip_markdown_fences(text) == "print('hi')"

    def test_strips_fence_without_language_tag(self):
        text = "```\nsome content\n```"
        assert _strip_markdown_fences(text) == "some content"

    def test_mismatched_fence_only_leading_is_stripped(self):
        # No closing fence at all: only the leading fence is removed.
        text = "```python\nprint('hi')"
        assert _strip_markdown_fences(text) == "print('hi')"

    def test_no_trailing_newline_before_closing_fence_is_not_stripped(self):
        # Trailing-fence regex requires a preceding newline; without it, the
        # closing ``` is left in place.
        text = "```\ncode```"
        assert _strip_markdown_fences(text) == "code```"

    def test_trailing_fence_with_trailing_whitespace_is_stripped(self):
        text = "```\ncode\n```   \n"
        assert _strip_markdown_fences(text) == "code"

    def test_multiline_body_preserved_between_fences(self):
        text = "```markdown\nline one\nline two\n```"
        assert _strip_markdown_fences(text) == "line one\nline two"

    def test_empty_fenced_block_leaves_closing_backticks(self):
        # Degenerate case verified against the actual implementation: the
        # leading-fence regex consumes the single newline shared by both
        # fences, so the trailing-fence regex (which requires its own
        # leading "\n") no longer has one to match against, and the closing
        # "```" is left in the output.
        text = "```\n```"
        assert _strip_markdown_fences(text) == "```"

    def test_language_tag_with_digits(self):
        text = "```html5\n<p>hi</p>\n```"
        assert _strip_markdown_fences(text) == "<p>hi</p>"


# ---------------------------------------------------------------------------
# _escape_triple_quotes
# ---------------------------------------------------------------------------


class TestEscapeTripleQuotes:
    def test_no_triple_quotes_unchanged(self):
        assert _escape_triple_quotes("hello world") == "hello world"

    def test_single_triple_quote_occurrence_escaped(self):
        assert _escape_triple_quotes('say """hi"""') == 'say \\"\\"\\"hi\\"\\"\\"'

    def test_multiple_triple_quote_occurrences_all_escaped(self):
        text = '"""first""" and """second"""'
        result = _escape_triple_quotes(text)
        assert '"""' not in result
        assert result.count('\\"\\"\\"') == 4

    def test_lone_double_quotes_are_untouched(self):
        # Only exact triple-quote runs are targeted; ordinary double quotes
        # (even multiple, non-adjacent ones) are left alone.
        assert _escape_triple_quotes('He said "hi" to "you"') == 'He said "hi" to "you"'

    def test_empty_string(self):
        assert _escape_triple_quotes("") == ""


# ---------------------------------------------------------------------------
# _map_sections
# ---------------------------------------------------------------------------


class TestMapSections:
    def test_canonical_key_passthrough(self):
        assert _map_sections({"role": "You are an agent."}) == {"role": "You are an agent."}

    def test_alias_key_maps_to_canonical(self):
        assert _map_sections({"persona": "You are an agent."}) == {"role": "You are an agent."}

    def test_multiple_aliases_map_to_same_canonical_field(self):
        assert _map_sections({"goal": "Ship the feature."}) == {"goals": "Ship the feature."}
        assert _map_sections({"objective": "Ship the feature."}) == {"goals": "Ship the feature."}
        assert _map_sections({"objectives": "Ship the feature."}) == {"goals": "Ship the feature."}

    def test_unknown_section_key_is_dropped(self):
        assert _map_sections({"random_header": "irrelevant"}) == {}

    def test_first_occurrence_wins_when_multiple_raw_keys_share_a_canonical(self):
        # Both "goals" and "goal" alias to the canonical "goals" field; the
        # first one encountered (dict insertion order) must win.
        sections = {"goals": "first content", "goal": "second content"}
        assert _map_sections(sections) == {"goals": "first content"}

    def test_constraints_family_of_aliases(self):
        for raw_key in ("constraints", "constraint", "rules", "rule", "limitations"):
            assert _map_sections({raw_key: "x"}) == {"constraints": "x"}

    def test_tech_stack_family_of_aliases(self):
        for raw_key in (
            "tech stack",
            "tech",
            "technology stack",
            "tools",
            "tools & capabilities",
            "tools and capabilities",
            "capabilities",
        ):
            assert _map_sections({raw_key: "x"}) == {"tech_stack": "x"}

    def test_workflows_family_of_aliases(self):
        for raw_key in ("workflows", "workflow", "steps"):
            assert _map_sections({raw_key: "x"}) == {"workflows": "x"}

    def test_empty_input_returns_empty_dict(self):
        assert _map_sections({}) == {}

    def test_mixed_known_and_unknown_keys(self):
        sections = {"role": "R", "unknown": "U", "goals": "G"}
        assert _map_sections(sections) == {"role": "R", "goals": "G"}


# ---------------------------------------------------------------------------
# _preview_order
# ---------------------------------------------------------------------------


class TestPreviewOrder:
    def test_returns_expected_fixed_order(self):
        assert _preview_order() == [
            "claude_md",
            "settings",
            "agents",
            "workflow",
            "mcp",
            "readme",
            "files",
        ]

    def test_claude_md_is_first_and_files_is_last(self):
        order = _preview_order()
        assert order[0] == "claude_md"
        assert order[-1] == "files"

    def test_is_deterministic_across_calls(self):
        assert _preview_order() == _preview_order()

    def test_returns_a_new_list_each_time(self):
        # Callers mutate the result (e.g. list-comprehension filtering); each
        # call must hand back an independent list, not a shared mutable object.
        first = _preview_order()
        first.append("mutated")
        assert "mutated" not in _preview_order()
