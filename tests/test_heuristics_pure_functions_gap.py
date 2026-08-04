"""Direct unit tests for pure heuristic helpers that were previously only
exercised indirectly through compile_text() integration tests.
"""
from app.heuristics import (
    detect_coding_context,
    detect_recency,
    extract_style_tone,
    generate_clarify_questions_struct,
)


# --- detect_recency ---------------------------------------------------


def test_detect_recency_english_keyword():
    assert detect_recency("Give me the latest news on this topic") is True


def test_detect_recency_turkish_keyword():
    assert detect_recency("Bugün için güncel bilgi lazım") is True


def test_detect_recency_no_match():
    assert detect_recency("Explain how binary search works") is False


def test_detect_recency_case_insensitive():
    assert detect_recency("BREAKING news just in") is True


# --- extract_style_tone -------------------------------------------------


def test_extract_style_tone_style_only():
    style, tone = extract_style_tone("Please keep it concise and structured")
    assert set(style) == {"concise", "structured"}
    assert tone == []


def test_extract_style_tone_tone_only():
    style, tone = extract_style_tone("Respond in a friendly and formal way")
    assert style == []
    assert set(tone) == {"friendly", "formal"}


def test_extract_style_tone_both():
    style, tone = extract_style_tone("Academic tone, please be objective")
    assert "academic" in style
    assert "objective" in tone


def test_extract_style_tone_neither():
    style, tone = extract_style_tone("Just answer the question")
    assert style == []
    assert tone == []


def test_extract_style_tone_case_insensitive():
    style, tone = extract_style_tone("CONCISE and FRIENDLY please")
    assert "concise" in style
    assert "friendly" in tone


# --- generate_clarify_questions_struct -----------------------------------


def test_generate_clarify_questions_struct_empty():
    assert generate_clarify_questions_struct([]) == []


def test_generate_clarify_questions_struct_unknown_term():
    assert generate_clarify_questions_struct(["not_a_real_term"]) == []


def test_generate_clarify_questions_struct_known_term():
    result = generate_clarify_questions_struct(["optimize"])
    assert len(result) == 1
    assert result[0]["term"] == "optimize"
    assert result[0]["category"] == "performance"
    assert "metric" in result[0]["question"]


def test_generate_clarify_questions_struct_capped_at_five():
    terms = ["optimize", "improve", "optimize", "improve", "optimize", "improve", "optimize"]
    result = generate_clarify_questions_struct(terms)
    assert len(result) <= 5


def test_generate_clarify_questions_struct_mixed_known_unknown():
    result = generate_clarify_questions_struct(["optimize", "totally_unknown", "improve"])
    terms_found = [entry["term"] for entry in result]
    assert terms_found == ["optimize", "improve"]


# --- detect_coding_context -----------------------------------------------


def test_detect_coding_context_explicit_code_request():
    assert detect_coding_context("Write a Python function to reverse a string") is True


def test_detect_coding_context_developer_persona_cue():
    assert detect_coding_context("As a developer, how should I refactor this?") is True


def test_detect_coding_context_no_match():
    assert detect_coding_context("What's the weather like today?") is False
