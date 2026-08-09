"""Direct unit tests for DomainHandler._inject_snippets and
DomainHandler._hash_id, which were previously only exercised indirectly
(if at all) through full compile_text() / analyze_domain() pipeline tests.

Follows the pattern established in
tests/heuristics/test_domain_expert_pure_helpers.py.
"""

from app.heuristics.handlers.domain_expert import DomainAnalysis, DomainHandler


def _new_analysis():
    return DomainAnalysis(detected_domain="coding")


# -----------------------------------------------------------------------------
# _inject_snippets
# -----------------------------------------------------------------------------


def test_inject_snippets_react_component_with_tailwind_adds_stack_suggestion():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets(
        "Write a react component using tailwind for styling", analysis
    )

    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "stack_recommendation"
    assert analysis.suggestions[0].priority == 70


def test_inject_snippets_react_code_with_tailwind_adds_stack_suggestion():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("Generate react code styled with tailwind", analysis)

    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "stack_recommendation"


def test_inject_snippets_react_without_tailwind_adds_nothing():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("Write a react component please", analysis)

    assert analysis.suggestions == []


def test_inject_snippets_react_and_tailwind_without_component_or_code_adds_nothing():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("I like react and tailwind a lot", analysis)

    assert analysis.suggestions == []


def test_inject_snippets_shadcn_keyword_adds_architecture_suggestion():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("Please use shadcn for the buttons", analysis)

    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "architecture"
    assert analysis.suggestions[0].priority == 65


def test_inject_snippets_ui_component_phrase_adds_architecture_suggestion():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("Build a reusable ui component for forms", analysis)

    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "architecture"


def test_inject_snippets_both_conditions_trigger_two_suggestions():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets(
        "Write a react component with tailwind and shadcn/ui", analysis
    )

    assert len(analysis.suggestions) == 2
    categories = {s.category for s in analysis.suggestions}
    assert categories == {"stack_recommendation", "architecture"}


def test_inject_snippets_no_relevant_keywords_leaves_analysis_untouched():
    handler = DomainHandler()
    analysis = _new_analysis()

    handler._inject_snippets("Write a Python function to sort a list", analysis)

    assert analysis.suggestions == []


# -----------------------------------------------------------------------------
# _hash_id
# -----------------------------------------------------------------------------


def test_hash_id_returns_ten_char_hex_prefix():
    handler = DomainHandler()
    result = handler._hash_id("hello")
    assert result == "aaf4c61ddc"
    assert len(result) == 10


def test_hash_id_empty_string():
    handler = DomainHandler()
    assert handler._hash_id("") == "da39a3ee5e"


def test_hash_id_is_deterministic():
    handler = DomainHandler()
    assert handler._hash_id("same input") == handler._hash_id("same input")


def test_hash_id_differs_for_different_inputs():
    handler = DomainHandler()
    assert handler._hash_id("input one") != handler._hash_id("input two")
