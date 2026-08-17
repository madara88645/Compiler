"""Direct unit coverage for app.heuristics._contains_any_keyword and the five
pure intent-detection wrappers built on top of it (detect_creative_intent,
detect_explanation_intent, detect_proposal_intent, detect_review_intent,
detect_preparation_intent). These feed downstream intent routing but are
only exercised indirectly today, so keyword-boundary and case-sensitivity
behavior has no direct assertions.
"""

from app.heuristics import (
    _contains_any_keyword,
    detect_creative_intent,
    detect_explanation_intent,
    detect_preparation_intent,
    detect_proposal_intent,
    detect_review_intent,
)


class TestContainsAnyKeyword:
    def test_returns_true_when_keyword_present(self):
        assert _contains_any_keyword("please write a short story", ["story", "poem"]) is True

    def test_returns_false_when_no_keyword_present(self):
        assert _contains_any_keyword("please write some code", ["story", "poem"]) is False

    def test_is_case_insensitive(self):
        assert _contains_any_keyword("Write me a STORY please", ["story"]) is True

    def test_empty_keyword_list_returns_false(self):
        assert _contains_any_keyword("anything at all", []) is False

    def test_empty_text_returns_false_for_nonempty_keywords(self):
        assert _contains_any_keyword("", ["story"]) is False

    def test_matches_as_substring_not_word_boundary(self):
        # "sue" is a substring of "issue" — _contains_any_keyword has no word
        # boundary, unlike the risk-keyword regex path elsewhere in this module.
        assert _contains_any_keyword("please file an issue", ["sue"]) is True

    def test_short_circuits_on_first_match(self):
        # Even if a later keyword would also match, the first hit is enough
        # to return True without raising for the remaining keywords.
        assert _contains_any_keyword("brainstorm names for my startup", ["brainstorm names", "poem"]) is True


class TestDetectCreativeIntent:
    def test_true_for_story_keyword(self):
        assert detect_creative_intent("write a short story about a dragon") is True

    def test_true_for_multi_word_keyword(self):
        assert detect_creative_intent("help me brainstorm names for my app") is True

    def test_false_for_unrelated_text(self):
        assert detect_creative_intent("deploy the app to production") is False

    def test_case_insensitive(self):
        assert detect_creative_intent("Write me a TAGLINE for launch") is True


class TestDetectExplanationIntent:
    def test_true_for_explain_keyword(self):
        assert detect_explanation_intent("can you explain how this works") is True

    def test_true_for_multi_word_keyword(self):
        assert detect_explanation_intent("walk me through the deployment process") is True

    def test_false_for_unrelated_text(self):
        assert detect_explanation_intent("write a poem about the sea") is False


class TestDetectProposalIntent:
    def test_true_for_proposal_keyword(self):
        assert detect_proposal_intent("draft a proposal for the new client") is True

    def test_true_for_pitch_keyword(self):
        assert detect_proposal_intent("help me pitch this idea") is True

    def test_false_for_unrelated_text(self):
        assert detect_proposal_intent("review my code for bugs") is False


class TestDetectReviewIntent:
    def test_true_for_review_keyword(self):
        assert detect_review_intent("please review this pull request") is True

    def test_true_for_check_my_keyword(self):
        assert detect_review_intent("check my essay for grammar mistakes") is True

    def test_false_for_unrelated_text(self):
        assert detect_review_intent("write a launch post for our product") is False


class TestDetectPreparationIntent:
    def test_true_for_interview_prep_keyword(self):
        assert detect_preparation_intent("interview prep for a software engineer role") is True

    def test_true_for_study_plan_keyword(self):
        assert detect_preparation_intent("build me a study plan for finals") is True

    def test_false_for_unrelated_text(self):
        assert detect_preparation_intent("audit this document for accuracy") is False

    def test_prepare_me_keyword_is_case_insensitive(self):
        assert detect_preparation_intent("PREPARE ME for the exam next week") is True
