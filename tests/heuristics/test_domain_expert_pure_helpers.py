"""Direct unit tests for DomainHandler's pure, regex/AST-based helpers.

These helpers (`_scan_for_secrets`, `_analyze_python_ast`) were previously only
exercised indirectly through full-pipeline `compile_text()` calls, which never
asserted on their specific branch/edge-case behavior. `_scan_for_secrets` in
particular is a security-relevant hardcoded-secret detector and had zero
coverage of any kind before this file.
"""

import re

from app.heuristics.handlers.domain_expert import DomainAnalysis, DomainHandler


def _new_analysis():
    return DomainAnalysis(detected_domain="coding")


# -----------------------------------------------------------------------------
# _scan_for_secrets
# -----------------------------------------------------------------------------


def test_scan_for_secrets_no_match_leaves_analysis_untouched():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._scan_for_secrets("just a normal prompt about writing a function", analysis)

    assert analysis.suggestions == []
    assert analysis.diagnostics == []


def test_scan_for_secrets_detects_generic_api_key_assignment():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._scan_for_secrets('api_key = "sk_test_1234567890abcdefghij"', analysis)

    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "security"
    assert analysis.suggestions[0].priority == 90
    assert len(analysis.diagnostics) == 1
    assert analysis.diagnostics[0].severity == "warning"
    assert analysis.diagnostics[0].category == "security"


def test_scan_for_secrets_detects_openai_style_key():
    handler = DomainHandler()
    analysis = _new_analysis()
    fake_key = "sk-" + "a" * 48

    handler._scan_for_secrets(f"use this key: {fake_key}", analysis)

    assert len(analysis.suggestions) == 1


def test_scan_for_secrets_detects_github_token():
    handler = DomainHandler()
    analysis = _new_analysis()
    fake_token = "ghp_" + "a" * 36

    handler._scan_for_secrets(f"token={fake_token}", analysis)

    assert len(analysis.suggestions) == 1


def test_scan_for_secrets_detects_credentials_in_url():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._scan_for_secrets(
        "connect to https://admin:password123@internal.example.com/db", analysis
    )

    assert len(analysis.suggestions) == 1


def test_scan_for_secrets_short_value_does_not_match_generic_pattern():
    handler = DomainHandler()
    analysis = _new_analysis()

    # Fewer than 20 chars after the assignment must not trigger the generic pattern.
    handler._scan_for_secrets('api_key = "short"', analysis)

    assert analysis.suggestions == []
    assert analysis.diagnostics == []


def test_scan_for_secrets_respects_additional_patterns():
    handler = DomainHandler()
    analysis = _new_analysis()
    custom_pattern = re.compile(r"CUSTOM-SECRET-\d+")

    handler._scan_for_secrets(
        "value is CUSTOM-SECRET-42", analysis, additional_patterns=[custom_pattern]
    )

    assert len(analysis.suggestions) == 1


# -----------------------------------------------------------------------------
# _analyze_python_ast
# -----------------------------------------------------------------------------


def test_analyze_python_ast_flags_missing_return_and_arg_hints():
    handler = DomainHandler()
    text = """```python
def add(a, b):
    return a + b
```"""

    suggestions, diagnostics = handler._analyze_python_ast(text)

    messages = [d.message for d in diagnostics]
    assert any("add" in m and "return type hint" in m for m in messages)
    assert any("'a'" in m and "missing type hint" in m for m in messages)
    assert any("'b'" in m and "missing type hint" in m for m in messages)
    assert suggestions == []


def test_analyze_python_ast_skips_init_return_hint_and_self():
    handler = DomainHandler()
    text = """```python
class Foo:
    def __init__(self, value):
        self.value = value
```"""

    suggestions, diagnostics = handler._analyze_python_ast(text)

    messages = [d.message for d in diagnostics]
    assert not any("__init__" in m and "return type hint" in m for m in messages)
    assert not any("'self'" in m for m in messages)
    assert any("'value'" in m for m in messages)


def test_analyze_python_ast_fully_typed_function_has_no_diagnostics():
    handler = DomainHandler()
    text = """```python
def add(a: int, b: int) -> int:
    return a + b
```"""

    suggestions, diagnostics = handler._analyze_python_ast(text)

    assert diagnostics == []


def test_analyze_python_ast_falls_back_to_bare_code_without_fence():
    handler = DomainHandler()
    text = "def greet(name):\n    return f'hi {name}'"

    suggestions, diagnostics = handler._analyze_python_ast(text)

    messages = [d.message for d in diagnostics]
    assert any("greet" in m for m in messages)


def test_analyze_python_ast_ignores_plain_prose_without_code_markers():
    handler = DomainHandler()
    text = "Please help me plan a birthday party for my friend."

    suggestions, diagnostics = handler._analyze_python_ast(text)

    assert suggestions == []
    assert diagnostics == []


def test_analyze_python_ast_swallows_syntax_errors_gracefully():
    handler = DomainHandler()
    text = """```python
def broken(:
```"""

    suggestions, diagnostics = handler._analyze_python_ast(text)

    assert suggestions == []
    assert diagnostics == []
