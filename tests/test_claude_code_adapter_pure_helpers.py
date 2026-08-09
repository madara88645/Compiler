"""Direct unit tests for small pure string-sanitization helpers in
app.adapters.claude_code: `_to_python_identifier`, `_escape_triple_quotes`,
and `_strip_markdown_fences`.

These were previously only exercised indirectly through the higher-level
`to_agent_sdk_python` / `to_claude_agent_sdk_multi` export tests.
"""

from app.adapters.claude_code import (
    _escape_triple_quotes,
    _strip_markdown_fences,
    _to_python_identifier,
)


# --- _to_python_identifier -------------------------------------------------


def test_to_python_identifier_simple_name():
    assert _to_python_identifier("My Skill") == "my_skill"


def test_to_python_identifier_replaces_non_alnum_with_underscore():
    assert _to_python_identifier("fetch-orders!!") == "fetch_orders"


def test_to_python_identifier_collapses_repeated_underscores():
    assert _to_python_identifier("a---b   c") == "a_b_c"


def test_to_python_identifier_strips_leading_and_trailing_underscores():
    assert _to_python_identifier("__hello__") == "hello"


def test_to_python_identifier_leading_digit_gets_prefixed():
    assert _to_python_identifier("123 go") == "skill_123_go"


def test_to_python_identifier_python_keyword_collision():
    assert _to_python_identifier("class") == "class_skill"


def test_to_python_identifier_another_keyword_collision():
    assert _to_python_identifier("import") == "import_skill"


def test_to_python_identifier_empty_string_falls_back_to_default():
    assert _to_python_identifier("") == "skill"


def test_to_python_identifier_all_symbols_falls_back_to_default():
    assert _to_python_identifier("!!!___...") == "skill"


# --- _escape_triple_quotes --------------------------------------------------


def test_escape_triple_quotes_escapes_all_occurrences():
    assert (
        _escape_triple_quotes('He said """hello""" to me')
        == 'He said \\"\\"\\"hello\\"\\"\\" to me'
    )


def test_escape_triple_quotes_no_triple_quotes_is_noop():
    assert _escape_triple_quotes("plain text with no fences") == "plain text with no fences"


def test_escape_triple_quotes_empty_string():
    assert _escape_triple_quotes("") == ""


# --- _strip_markdown_fences --------------------------------------------------


def test_strip_markdown_fences_removes_language_tagged_fence():
    text = "```python\nprint('hi')\n```"
    assert _strip_markdown_fences(text) == "print('hi')"


def test_strip_markdown_fences_removes_bare_fence():
    text = "```\nsome content\n```"
    assert _strip_markdown_fences(text) == "some content"


def test_strip_markdown_fences_strips_surrounding_whitespace():
    text = "   ```\ncontent\n```   "
    assert _strip_markdown_fences(text) == "content"


def test_strip_markdown_fences_no_fences_is_unchanged():
    assert _strip_markdown_fences("just plain text") == "just plain text"


def test_strip_markdown_fences_only_strips_leading_and_trailing_fences():
    text = "```js\nconst x = '```not a fence```';\n```"
    assert _strip_markdown_fences(text) == "const x = '```not a fence```';"
