"""Coverage for PromptComparison.calculate_similarity, a thin wrapper around
difflib.SequenceMatcher.ratio() * 100 that had no direct test.
"""

import pytest

from app.prompt_diff import PromptComparison


@pytest.fixture
def comparator():
    """PromptComparison instance without running __init__ (pure method under test)."""
    return PromptComparison.__new__(PromptComparison)


def test_calculate_similarity_identical_strings_is_100(comparator):
    assert comparator.calculate_similarity("hello world", "hello world") == 100.0


def test_calculate_similarity_both_empty_is_100(comparator):
    assert comparator.calculate_similarity("", "") == 100.0


def test_calculate_similarity_completely_different_strings_is_low(comparator):
    score = comparator.calculate_similarity("hello world", "xyz completely different")
    assert score == pytest.approx(22.857142857142858)
    assert score < 50.0


def test_calculate_similarity_one_empty_string_is_zero(comparator):
    assert comparator.calculate_similarity("abc", "") == 0.0


def test_calculate_similarity_partial_overlap_is_between_0_and_100(comparator):
    score = comparator.calculate_similarity("The quick brown fox", "The quick red fox")
    assert score == pytest.approx(83.33333333333334)
    assert 0.0 < score < 100.0
