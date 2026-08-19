"""Direct unit tests for two pure regex helpers in
app.heuristics.handlers.exploration: `_compile_patterns` and `_first_match`.
"""

from __future__ import annotations

import re

from app.heuristics.handlers.exploration import _compile_patterns, _first_match


class TestCompilePatterns:
    def test_returns_tuple_of_compiled_patterns(self):
        patterns = _compile_patterns(("bug", "crash"))
        assert len(patterns) == 2
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_empty_markers_returns_empty_tuple(self):
        assert _compile_patterns(()) == ()

    def test_pattern_matches_whole_word_only(self):
        (pattern,) = _compile_patterns(("bug",))
        assert pattern.search("there is a bug here")
        assert pattern.search("debugging this code") is None

    def test_pattern_escapes_regex_special_characters_in_marker(self):
        (pattern,) = _compile_patterns(("stack trace",))
        assert pattern.search("here is the stack trace output")
        assert pattern.search("stackXtrace") is None


class TestFirstMatch:
    def test_returns_first_marker_whose_pattern_matches_in_list_order(self):
        markers = ("crash", "bug")
        patterns = _compile_patterns(markers)
        # Text contains "bug" first positionally, but "crash" is first in
        # marker/pattern order, so it must win.
        text = "there's a bug that causes a crash"
        assert _first_match(patterns, markers, text) == "crash"

    def test_returns_none_when_nothing_matches(self):
        markers = ("crash", "bug")
        patterns = _compile_patterns(markers)
        assert _first_match(patterns, markers, "everything is fine") is None

    def test_empty_patterns_returns_none(self):
        assert _first_match((), (), "any text") is None

    def test_matches_second_marker_when_first_absent(self):
        markers = ("crash", "bug")
        patterns = _compile_patterns(markers)
        assert _first_match(patterns, markers, "there is a bug") == "bug"
