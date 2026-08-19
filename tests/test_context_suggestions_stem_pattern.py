"""Direct unit tests for app.heuristics.handlers.context_suggestions._get_stem_pattern.

Builds (and lru_caches) a word-boundary regex Pattern from a filename stem.
"""

from __future__ import annotations

import re

from app.heuristics.handlers.context_suggestions import _get_stem_pattern


def test_returns_compiled_pattern():
    pattern = _get_stem_pattern("auth")
    assert isinstance(pattern, re.Pattern)


def test_matches_stem_as_whole_word():
    pattern = _get_stem_pattern("auth")
    assert pattern.search("check the auth logic")


def test_does_not_match_as_substring_of_longer_word():
    pattern = _get_stem_pattern("auth")
    assert pattern.search("authentication service") is None


def test_caching_returns_identical_object_for_same_stem():
    first = _get_stem_pattern("billing")
    second = _get_stem_pattern("billing")
    assert first is second


def test_different_stems_produce_different_patterns():
    a = _get_stem_pattern("orders")
    b = _get_stem_pattern("payments")
    assert a is not b

def test_regex_special_characters_in_stem_are_escaped():
    pattern = _get_stem_pattern("a.b")
    assert pattern.search("look at a.b now")
    assert pattern.search("look at aXb now") is None
