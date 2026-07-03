import pytest

from app.heuristics.handlers.content import ContentHandler
from app.models import IR
from app.models_v2 import IRv2


@pytest.fixture
def handler():
    return ContentHandler()


def _ir(metadata=None, tools=None) -> IR:
    return IR(
        language="en",
        persona="assistant",
        role="AI Assistant",
        domain="general",
        goals=[],
        tasks=[],
        tools=tools or [],
        output_format="markdown",
        length_hint="medium",
        metadata=metadata or {},
    )


def _run(handler, metadata=None, tools=None):
    ir_v1 = _ir(metadata=metadata, tools=tools)
    ir_v2 = IRv2()
    handler.handle(ir_v2, ir_v1)
    return ir_v2


# --------------------------------------------------------------------------
# Metadata-flag-driven intents
# --------------------------------------------------------------------------


def test_summary_flag_adds_summary_intent(handler):
    ir_v2 = _run(handler, metadata={"summary": "true"})
    assert "summary" in ir_v2.intents


def test_summary_flag_string_false_does_not_add_summary(handler):
    ir_v2 = _run(handler, metadata={"summary": "false"})
    assert "summary" not in ir_v2.intents


def test_comparison_items_adds_compare_intent(handler):
    ir_v2 = _run(handler, metadata={"comparison_items": ["A", "B"]})
    assert "compare" in ir_v2.intents


def test_empty_comparison_items_does_not_add_compare(handler):
    ir_v2 = _run(handler, metadata={"comparison_items": []})
    assert "compare" not in ir_v2.intents


def test_variant_count_greater_than_one_adds_variants_intent(handler):
    ir_v2 = _run(handler, metadata={"variant_count": 3})
    assert "variants" in ir_v2.intents


def test_variant_count_of_one_does_not_add_variants(handler):
    ir_v2 = _run(handler, metadata={"variant_count": 1})
    assert "variants" not in ir_v2.intents


def test_variant_count_missing_defaults_to_one_no_variants(handler):
    ir_v2 = _run(handler, metadata={})
    assert "variants" not in ir_v2.intents


def test_code_request_adds_code_intent(handler):
    ir_v2 = _run(handler, metadata={"code_request": True})
    assert "code" in ir_v2.intents


def test_no_code_request_key_no_code_intent(handler):
    ir_v2 = _run(handler, metadata={})
    assert "code" not in ir_v2.intents


def test_ambiguous_terms_adds_ambiguous_intent(handler):
    ir_v2 = _run(handler, metadata={"ambiguous_terms": ["it"]})
    assert "ambiguous" in ir_v2.intents


def test_web_tool_adds_recency_intent(handler):
    ir_v2 = _run(handler, metadata={}, tools=["web"])
    assert "recency" in ir_v2.intents


def test_no_web_tool_no_recency_intent(handler):
    ir_v2 = _run(handler, metadata={}, tools=["code_interpreter"])
    assert "recency" not in ir_v2.intents


# --------------------------------------------------------------------------
# original_text-driven intents (regex/keyword detectors)
# --------------------------------------------------------------------------


def test_creative_intent_detected(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Write a short story about a dragon."})
    assert "creative" in ir_v2.intents


def test_explanation_intent_detected(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Can you explain how does this algorithm work?"})
    assert "explanation" in ir_v2.intents


def test_proposal_intent_detected(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Write a proposal for the new marketing plan."})
    assert "proposal" in ir_v2.intents


def test_review_intent_detected(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Please review my essay for grammar mistakes."})
    assert "review" in ir_v2.intents


def test_preparation_intent_detected(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Prepare me for my upcoming interview prep."})
    assert "preparation" in ir_v2.intents


def test_troubleshooting_intent_detected_via_keyword(handler):
    ir_v2 = _run(handler, metadata={"original_text": "Help me troubleshoot this failing build."})
    assert "troubleshooting" in ir_v2.intents


def test_troubleshooting_intent_detected_via_live_debug(handler):
    # detect_troubleshooting_intent also triggers off detect_live_debug();
    # a stack trace / traceback is one of the TROUBLESHOOTING_INTENT_KEYWORDS
    ir_v2 = _run(handler, metadata={"original_text": "Here is the traceback I'm seeing, please help."})
    assert "troubleshooting" in ir_v2.intents


def test_no_original_text_skips_regex_intents(handler):
    ir_v2 = _run(handler, metadata={})
    for intent in (
        "creative",
        "explanation",
        "proposal",
        "review",
        "preparation",
        "troubleshooting",
    ):
        assert intent not in ir_v2.intents


def test_plain_text_with_no_keywords_adds_no_intents(handler):
    ir_v2 = _run(handler, metadata={"original_text": "The weather is nice today."})
    assert ir_v2.intents == []


# --------------------------------------------------------------------------
# Combined / multiple intents at once
# --------------------------------------------------------------------------


def test_multiple_intents_all_appended_in_order(handler):
    ir_v2 = _run(
        handler,
        metadata={
            "summary": "true",
            "comparison_items": ["A", "B"],
            "variant_count": 2,
            "code_request": True,
            "original_text": "Explain how does recursion work, then review my code.",
        },
        tools=["web"],
    )

    assert ir_v2.intents == [
        "summary",
        "compare",
        "variants",
        "code",
        "recency",
        "explanation",
        "review",
    ]
