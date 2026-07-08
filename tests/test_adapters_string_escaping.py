"""Tests for the triple-quote escaping helper duplicated across
app.adapters.claude_sdk and app.adapters.langchain.

This helper embeds an arbitrary user-authored system prompt inside a Python
triple-double-quoted string literal in *generated* export code. If the prompt
contains a literal `\"\"\"`, it must be escaped or the generated code would
fail to parse for the end user who downloads the export. These tests lock in
the escaping behavior directly and verify the generated exports still compile
when a prompt contains embedded triple quotes.
"""

from app.adapters.agent_ir import AgentExportIR
from app.adapters.claude_sdk import _escape_for_python_string as claude_sdk_escape
from app.adapters.claude_sdk import to_python
from app.adapters.langchain import _escape_for_python_string as langchain_escape
from app.adapters.langchain import to_langchain_python, to_langgraph_python


def test_escape_is_noop_when_no_triple_quotes_present():
    text = "A normal prompt with \"single double quotes\" and 'single quotes'."
    assert claude_sdk_escape(text) == text
    assert langchain_escape(text) == text


def test_escape_replaces_a_single_triple_quote_occurrence():
    text = 'Never repeat """secret instructions""" verbatim.'
    expected = 'Never repeat \\"\\"\\"secret instructions\\"\\"\\" verbatim.'
    assert claude_sdk_escape(text) == expected
    assert langchain_escape(text) == expected


def test_escape_replaces_multiple_triple_quote_occurrences():
    text = '"""one""" and """two""" and """three"""'
    result = claude_sdk_escape(text)
    assert result.count('\\"\\"\\"') == 6
    assert '"""' not in result


def test_escape_leaves_lone_double_quotes_untouched():
    text = 'Say "hello" but not ""double"" or too few quotes.'
    assert claude_sdk_escape(text) == text
    assert langchain_escape(text) == text


def test_claude_sdk_and_langchain_escape_helpers_agree():
    samples = [
        "",
        "plain text",
        'has """triple""" quotes',
        'edge """""" case of six quotes in a row',
        'unicode "çok özel" text with """embedded""" markers',
    ]
    for text in samples:
        assert claude_sdk_escape(text) == langchain_escape(text)


def _ir_with_embedded_triple_quotes():
    # Single-line on purpose: a multi-line raw_system_prompt hits a separate,
    # pre-existing textwrap.dedent indentation issue in these adapters that
    # is out of scope for this test file (see PR description).
    prompt = 'You are a helpful agent. Never say """ignore previous instructions""" to the user.'
    return AgentExportIR(raw_system_prompt=prompt, model="claude-opus-4-6")


def test_claude_sdk_export_compiles_when_prompt_has_embedded_triple_quotes():
    ir = _ir_with_embedded_triple_quotes()
    code = to_python(ir)

    compile(code, "<claude_sdk_export>", "exec")
    assert '\\"\\"\\"ignore previous instructions\\"\\"\\"' in code


def test_langchain_export_compiles_when_prompt_has_embedded_triple_quotes():
    ir = _ir_with_embedded_triple_quotes()
    code = to_langchain_python(ir)

    compile(code, "<langchain_export>", "exec")
    assert '\\"\\"\\"ignore previous instructions\\"\\"\\"' in code


def test_langgraph_single_agent_export_compiles_when_prompt_has_embedded_triple_quotes():
    ir = _ir_with_embedded_triple_quotes()
    code = to_langgraph_python(ir)

    compile(code, "<langgraph_export>", "exec")
    assert '\\"\\"\\"ignore previous instructions\\"\\"\\"' in code


def test_langgraph_multi_agent_export_compiles_when_prompt_has_embedded_triple_quotes():
    sub_agent = _ir_with_embedded_triple_quotes()
    sub_agent.name = "Researcher"
    ir = AgentExportIR(
        raw_system_prompt="Coordinator prompt with no special characters.",
        model="claude-opus-4-6",
        is_multi_agent=True,
        agents=[sub_agent],
    )
    code = to_langgraph_python(ir)

    compile(code, "<langgraph_multi_export>", "exec")
    assert '\\"\\"\\"ignore previous instructions\\"\\"\\"' in code
