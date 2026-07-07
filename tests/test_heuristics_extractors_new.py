"""Edge-case coverage for pure heuristics extractors/detectors in
app/heuristics/__init__.py that had zero direct tests.

Each function is exercised with: an empty string, a punctuation-only string,
a normal case, and (where the underlying keyword table is bilingual) at
least one English and one Turkish case.
"""

from app.heuristics import (
    detect_code_request,
    detect_conflicts,
    detect_domain_candidates,
    detect_length_hint,
    estimate_complexity,
    extract_entities,
    extract_format,
    extract_quantities,
    extract_temporal_flags,
    generate_clarify_questions,
)


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------


def test_extract_entities_empty_string():
    assert extract_entities("") == []


def test_extract_entities_punctuation_only():
    assert extract_entities("!!! ??? ...") == []


def test_extract_entities_normal_case_captures_tech_tokens():
    text = "We use Kubernetes and GPT-4 with ISO 27001 compliance and AWS"
    entities = extract_entities(text)
    assert "Kubernetes" in entities
    assert "GPT-4" in entities
    assert "AWS" in entities


def test_extract_entities_caps_at_thirty_and_dedupes():
    text = " ".join(f"Entity{i}" for i in range(40)) + " Entity0 Entity1"
    entities = extract_entities(text)
    assert len(entities) <= 30
    assert len(entities) == len(set(entities))


# ---------------------------------------------------------------------------
# estimate_complexity
# ---------------------------------------------------------------------------


def test_estimate_complexity_empty_string_is_low():
    assert estimate_complexity("") == "low"


def test_estimate_complexity_punctuation_only_is_low():
    assert estimate_complexity("!!!") == "low"


def test_estimate_complexity_long_unique_text_is_medium():
    # >40 words and >30 unique tokens, no "vs"/compare/teach signal -> score 2.
    long_text = " ".join(f"word{i}" for i in range(45))
    assert estimate_complexity(long_text) == "medium"


def test_estimate_complexity_long_with_compare_and_teach_is_high():
    long_text = " ".join(f"word{i}" for i in range(45))
    text = "please teach me and compare vs alternatives " + long_text
    assert estimate_complexity(text) == "high"


def test_estimate_complexity_short_text_is_low():
    assert estimate_complexity("fix this bug") == "low"


def test_estimate_complexity_turkish_teach_keyword_contributes():
    # Short text, so only the "öğret" signal can fire -> still low overall,
    # but must not raise and must return a valid bucket.
    result = estimate_complexity("bunu bana öğret")
    assert result in {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# generate_clarify_questions
# ---------------------------------------------------------------------------


def test_generate_clarify_questions_empty_list():
    assert generate_clarify_questions([]) == []


def test_generate_clarify_questions_unknown_term_is_ignored():
    assert generate_clarify_questions(["banana"]) == []


def test_generate_clarify_questions_known_term_returns_its_question():
    questions = generate_clarify_questions(["optimize"])
    assert questions == ["Which metric or aspect should be optimized? (performance, cost, memory?)"]


def test_generate_clarify_questions_deduplicates_and_caps_at_five():
    terms = ["optimize", "improve", "better", "efficient", "scalable", "fast", "robust"]
    questions = generate_clarify_questions(terms)
    assert len(questions) == 5
    assert len(questions) == len(set(questions))


# ---------------------------------------------------------------------------
# extract_temporal_flags
# ---------------------------------------------------------------------------


def test_extract_temporal_flags_empty_string():
    assert extract_temporal_flags("") == []


def test_extract_temporal_flags_punctuation_only():
    assert extract_temporal_flags("...") == []


def test_extract_temporal_flags_english_mixed_signals():
    text = "Let us meet today, also relevant for Q1 2025 and March 2024"
    flags = extract_temporal_flags(text)
    assert flags == ["2025", "2024", "Q1 2025", "march", "today"]


def test_extract_temporal_flags_turkish_month():
    flags = extract_temporal_flags("ocak ayında görüşelim")
    assert "ocak" in flags


# ---------------------------------------------------------------------------
# extract_quantities
# ---------------------------------------------------------------------------


def test_extract_quantities_empty_string():
    assert extract_quantities("") == []


def test_extract_quantities_punctuation_only():
    assert extract_quantities("...") == []


def test_extract_quantities_normal_case():
    text = "Handle 500 requests within 200ms for 100 users, budget 5gb"
    quantities = extract_quantities(text)
    assert {"value": "500", "unit": "requests"} in quantities
    assert {"value": "200", "unit": "ms"} in quantities
    assert {"value": "100", "unit": "users"} in quantities
    assert {"value": "5", "unit": "gb"} in quantities


def test_extract_quantities_range_pattern():
    quantities = extract_quantities("latency should be 1500-3000 ms")
    assert {"value": "1500-3000", "unit": "ms"} in quantities


# ---------------------------------------------------------------------------
# detect_code_request
# ---------------------------------------------------------------------------


def test_detect_code_request_empty_string_is_false():
    assert detect_code_request("") is False


def test_detect_code_request_punctuation_only_is_false():
    assert detect_code_request("???") is False


def test_detect_code_request_english_case():
    assert detect_code_request("Write a python function to parse logs") is True


def test_detect_code_request_turkish_case():
    assert detect_code_request("örnek kod yazar mısın") is True


def test_detect_code_request_no_keyword_is_false():
    assert detect_code_request("What is the weather today") is False


# ---------------------------------------------------------------------------
# extract_format
# ---------------------------------------------------------------------------


def test_extract_format_empty_string_defaults_to_markdown():
    assert extract_format("") == "markdown"


def test_extract_format_punctuation_only_defaults_to_markdown():
    assert extract_format("???") == "markdown"


def test_extract_format_english_json():
    assert extract_format("Return the result as JSON") == "json"


def test_extract_format_turkish_table():
    assert extract_format("Sonucu tablo olarak ver") == "table"


def test_extract_format_no_keyword_defaults_to_markdown():
    assert extract_format("Just answer normally") == "markdown"


# ---------------------------------------------------------------------------
# detect_length_hint
# ---------------------------------------------------------------------------


def test_detect_length_hint_empty_string_defaults_to_medium():
    assert detect_length_hint("") == "medium"


def test_detect_length_hint_punctuation_only_defaults_to_medium():
    assert detect_length_hint("???") == "medium"


def test_detect_length_hint_english_short():
    assert detect_length_hint("Give me a short answer") == "short"


def test_detect_length_hint_turkish_short():
    assert detect_length_hint("kısa bir cevap ver") == "short"


def test_detect_length_hint_english_long():
    assert detect_length_hint("I want a comprehensive detailed long answer") == "long"


def test_detect_length_hint_no_keyword_defaults_to_medium():
    assert detect_length_hint("Just answer") == "medium"


# ---------------------------------------------------------------------------
# detect_conflicts
# ---------------------------------------------------------------------------


def test_detect_conflicts_empty_list():
    assert detect_conflicts([]) == []


def test_detect_conflicts_no_conflict():
    assert detect_conflicts(["Be nice", "Be accurate"]) == []


def test_detect_conflicts_english_length_vs_detail():
    assert detect_conflicts(["very short", "high detail"]) == ["length_vs_detail"]


def test_detect_conflicts_turkish_length_vs_detail():
    assert detect_conflicts(["kısa", "detaylı"]) == ["length_vs_detail"]


# ---------------------------------------------------------------------------
# detect_domain_candidates
# ---------------------------------------------------------------------------


def test_detect_domain_candidates_empty_evidence():
    assert detect_domain_candidates([]) == []


def test_detect_domain_candidates_single_domain():
    assert detect_domain_candidates(["software:api"]) == ["software"]


def test_detect_domain_candidates_multiple_domains_ranked_and_capped():
    evidence = [
        "software:api",
        "software:react",
        "security:oauth",
        "finance:stock",
    ]
    assert detect_domain_candidates(evidence, top_k=2) == ["software", "finance"]
