"""Direct unit tests for DomainHandler's domain analyzers and router.

These functions (`_analyze_business`, `_analyze_education`, `_analyze_data_science`,
`_analyze_creative_writing`, `_detect_story_structure`, and `analyze_domain`) were
previously only exercised indirectly through full-pipeline `compile_text()` calls,
which never asserted on their specific branch/edge-case behavior. This file gives
each a handful of deterministic, well-chosen inputs -- a case that should trigger
detection, and a case that should not -- and asserts against the real returned
fields.

`detect_implied_persona` already has partial direct coverage in
`tests/test_regex_precompilation.py` (single-match base confidence and
specificity tie-break, via different example inputs). The cases added here
that are NOT covered there: multiple-match confidence scaling, the no-match
fallback, and the position-based tie-break.
"""

import pytest

from app.heuristics.handlers.domain_expert import (
    DOMAIN_RULES,
    DomainHandler,
)


# -----------------------------------------------------------------------------
# _analyze_business
# -----------------------------------------------------------------------------


def test_analyze_business_flags_all_missing_required_elements():
    handler = DomainHandler()
    text = "We need a plan for our project next year."

    analysis = handler._analyze_business(text, text.lower())

    assert analysis.detected_domain == "business"
    # BLUF suggestion is always first, plus one suggestion per missing element
    # (kpis, timeline, stakeholders, budget).
    assert len(analysis.suggestions) == 5
    assert analysis.suggestions[0].category == "format"
    categories = [s.category for s in analysis.suggestions]
    assert "metrics" in categories
    assert "planning" in categories
    assert "governance" in categories
    assert "financial" in categories
    assert len(analysis.diagnostics) == 4
    assert all(d.category == "completeness" for d in analysis.diagnostics)
    assert "frameworks" not in analysis.detected_patterns


def test_analyze_business_suppresses_suggestions_when_elements_present_and_detects_framework():
    handler = DomainHandler()
    text = (
        "Our business strategy includes kpi tracking, a deadline for delivery, "
        "stakeholder alignment, and budget planning. We will use a SWOT analysis."
    )

    analysis = handler._analyze_business(text, text.lower())

    # Only the always-on BLUF suggestion remains; every required element was mentioned.
    assert len(analysis.suggestions) == 1
    assert analysis.suggestions[0].category == "format"
    assert analysis.diagnostics == []
    assert analysis.detected_patterns.get("frameworks") == ["swot"]


# -----------------------------------------------------------------------------
# _analyze_education
# -----------------------------------------------------------------------------


def test_analyze_education_detects_beginner_level_and_feynman_technique():
    handler = DomainHandler()
    text = "Explain this to a beginner, eli5 please."

    analysis = handler._analyze_education(text, text.lower())

    assert analysis.detected_domain == "education"
    assert analysis.sub_domain == "beginner"
    # 3 beginner-level suggestions + 1 feynman suggestion.
    assert len(analysis.suggestions) == 4
    assert analysis.detected_patterns.get("pedagogy") == ["feynman"]


def test_analyze_education_no_indicators_yields_empty_analysis():
    handler = DomainHandler()
    text = "Please write a report about quarterly sales."

    analysis = handler._analyze_education(text, text.lower())

    assert analysis.sub_domain is None
    assert analysis.suggestions == []
    assert analysis.detected_patterns == {}


# -----------------------------------------------------------------------------
# _analyze_data_science
# -----------------------------------------------------------------------------


def test_analyze_data_science_flags_all_missing_checks():
    handler = DomainHandler()
    text = "Build me something cool please."

    analysis = handler._analyze_data_science(text, text.lower())

    assert analysis.detected_domain == "data_science"
    categories = sorted(s.category for s in analysis.suggestions)
    assert categories == ["data_prep", "ethics", "evaluation"]


def test_analyze_data_science_no_suggestions_when_all_checks_addressed():
    handler = DomainHandler()
    text = "clean the data, check for bias and fairness, then measure accuracy and precision"

    analysis = handler._analyze_data_science(text, text.lower())

    assert analysis.suggestions == []


# -----------------------------------------------------------------------------
# _detect_story_structure
# -----------------------------------------------------------------------------


def test_detect_story_structure_heros_journey():
    handler = DomainHandler()
    structures = DOMAIN_RULES["creative_writing"]["structures"]
    text_lower = "our hero begins an epic journey and adventure, guided by a wise mentor."

    assert handler._detect_story_structure(text_lower, structures) == "heros_journey"


def test_detect_story_structure_three_act():
    handler = DomainHandler()
    structures = DOMAIN_RULES["creative_writing"]["structures"]
    text_lower = "act one is the setup, act two is confrontation, act three is the resolution."

    assert handler._detect_story_structure(text_lower, structures) == "three_act"


def test_detect_story_structure_save_the_cat():
    handler = DomainHandler()
    structures = DOMAIN_RULES["creative_writing"]["structures"]
    text_lower = (
        "following the save the cat beat sheet, the opening image sets the theme stated clearly."
    )

    assert handler._detect_story_structure(text_lower, structures) == "save_the_cat"


def test_detect_story_structure_no_match_returns_none():
    handler = DomainHandler()
    structures = DOMAIN_RULES["creative_writing"]["structures"]
    text_lower = "just a plain description with no structure indicators."

    assert handler._detect_story_structure(text_lower, structures) is None


# -----------------------------------------------------------------------------
# _analyze_creative_writing
# -----------------------------------------------------------------------------


def test_analyze_creative_writing_no_structure_no_style_issues():
    handler = DomainHandler()
    text = "Write about a quiet town by the sea with a calm river."

    analysis = handler._analyze_creative_writing(text, text.lower())

    assert analysis.sub_domain is None
    # Only the 4 always-on universal suggestions.
    assert len(analysis.suggestions) == 4
    assert analysis.diagnostics == []
    assert analysis.detected_patterns == {}


def test_analyze_creative_writing_suggests_structure_when_plot_keyword_present():
    handler = DomainHandler()
    text = "I want to write a story with several chapters."

    analysis = handler._analyze_creative_writing(text, text.lower())

    assert analysis.sub_domain is None
    assert any(s.category == "structure" for s in analysis.suggestions)


def test_analyze_creative_writing_detects_structure_sets_sub_domain_and_pattern():
    handler = DomainHandler()
    text = "our hero begins an epic journey and adventure, guided by a wise mentor."

    analysis = handler._analyze_creative_writing(text, text.lower())

    assert analysis.sub_domain == "heros_journey"
    assert analysis.detected_patterns.get("structure") == ["heros_journey"]
    # Structure was detected, so the generic "consider a structure" nudge is skipped.
    assert not any(s.category == "structure" for s in analysis.suggestions)


def test_analyze_creative_writing_flags_adverb_overuse():
    handler = DomainHandler()
    text = "He slowly walked quickly and quietly away sadly."

    analysis = handler._analyze_creative_writing(text, text.lower())

    assert any("adverb" in s.text.lower() for s in analysis.suggestions)
    assert len(analysis.diagnostics) == 1
    assert analysis.diagnostics[0].category == "style"
    assert "4 adverbs" in analysis.diagnostics[0].message
    assert analysis.detected_patterns.get("adverbs") == [
        "slowly",
        "quickly",
        "quietly",
        "sadly",
    ]


def test_analyze_creative_writing_flags_filter_words():
    handler = DomainHandler()
    text = "She felt cold as the wind blew."

    analysis = handler._analyze_creative_writing(text, text.lower())

    assert analysis.detected_patterns.get("filter_words") == ["felt"]
    assert any(s.category == "style" and "filter" in s.text.lower() for s in analysis.suggestions)


# -----------------------------------------------------------------------------
# analyze_domain (public router)
# -----------------------------------------------------------------------------


def test_analyze_domain_maps_software_hint_to_coding():
    handler = DomainHandler()

    analysis = handler.analyze_domain("some arbitrary text here", domain_hint="software")

    assert analysis.detected_domain == "coding"


def test_analyze_domain_infrastructure_hint_falls_through_to_generic_analysis():
    handler = DomainHandler()

    analysis = handler.analyze_domain("some arbitrary text", domain_hint="infrastructure")

    assert analysis.detected_domain == "infrastructure"
    assert analysis.suggestions == []
    assert analysis.diagnostics == []
    assert analysis.sub_domain is None


def test_analyze_domain_defaults_to_general_when_no_keywords_or_hint():
    handler = DomainHandler()

    analysis = handler.analyze_domain("asdf qwer zxcv poiu")

    assert analysis.detected_domain == "general"
    assert analysis.suggestions == []


def test_analyze_domain_routes_business_hint_to_business_analyzer():
    handler = DomainHandler()

    analysis = handler.analyze_domain(
        "random filler text with nothing special", domain_hint="business"
    )

    assert analysis.detected_domain == "business"
    assert any(s.category == "format" for s in analysis.suggestions)


def test_analyze_domain_auto_detects_coding_from_keywords_without_hint():
    handler = DomainHandler()
    text = "Write a function to implement an algorithm; handle the error and write a unit test."

    analysis = handler.analyze_domain(text)

    assert analysis.detected_domain == "coding"


# -----------------------------------------------------------------------------
# detect_implied_persona
# -----------------------------------------------------------------------------


def test_detect_implied_persona_single_match_gives_base_confidence():
    handler = DomainHandler()

    persona, confidence = handler.detect_implied_persona("def foo(): pass")

    assert persona == "Python Developer"
    assert confidence == pytest.approx(0.6)


def test_detect_implied_persona_multiple_matches_increase_confidence():
    handler = DomainHandler()
    text = "def foo(): pass\ndef bar(): pass\ndef baz(): pass"

    persona, confidence = handler.detect_implied_persona(text)

    assert persona == "Python Developer"
    assert confidence == pytest.approx(0.8)


def test_detect_implied_persona_prefers_more_specific_keyword_on_score_tie():
    handler = DomainHandler()
    # Both "roi" and "swot" occur once (tied score); "swot" is the longer/more
    # specific keyword and should win the tie-break.
    text = "Let's calculate the roi and complete a swot analysis."

    persona, confidence = handler.detect_implied_persona(text)

    assert persona == "Business Consultant"
    assert confidence == pytest.approx(0.6)


def test_detect_implied_persona_prefers_later_position_on_full_tie():
    handler = DomainHandler()
    # "git" (-> Software Engineer) and "roi" (-> Business Analyst) are both
    # length-3 keywords appearing once each (score and specificity tied).
    # "roi" occurs later in the text and should win the tie-break.
    text = "Use Git for version control, then check the ROI."

    persona, confidence = handler.detect_implied_persona(text)

    assert persona == "Business Analyst"
    assert confidence == pytest.approx(0.6)


def test_detect_implied_persona_no_match_returns_none_and_zero_confidence():
    handler = DomainHandler()

    persona, confidence = handler.detect_implied_persona("The weather is nice today.")

    assert persona is None
    assert confidence == 0.0
