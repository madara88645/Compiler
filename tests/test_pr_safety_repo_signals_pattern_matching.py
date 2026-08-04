"""Direct coverage for the private pattern-matching and path-safety helpers
in ``app.pr_safety.repo_signals``.

``_matches_repo_pattern``, ``_matches_any_repo_pattern``,
``_matches_ordered_patterns``, and ``_is_safe_relative_path`` are the
security-adjacent primitives behind CODEOWNERS matching and GitHub Actions
``paths``/``paths-ignore`` evaluation. Prior to this file they only had
indirect coverage via ``collect_repo_signals`` integration tests in
``tests/test_pr_safety_repo_signals.py``. These tests exercise the helpers
directly, especially path-traversal and anchoring edge cases.
"""

from app.pr_safety.repo_signals import (
    _is_safe_relative_path,
    _matches_any_repo_pattern,
    _matches_ordered_patterns,
    _matches_repo_pattern,
)


# --------------------------------------------------------------------------
# _matches_repo_pattern
# --------------------------------------------------------------------------


def test_matches_repo_pattern_unanchored_star_matches_extension_anywhere():
    assert _matches_repo_pattern("app/nested/foo.py", "*.py") is True


def test_matches_repo_pattern_unanchored_bare_filename_matches_any_depth():
    # A pattern with no "/" acts like a gitignore basename rule: it matches
    # the file at any directory depth, not just at the repo root.
    assert _matches_repo_pattern("app/sub/foo.py", "foo.py") is True
    assert _matches_repo_pattern("foo.py", "foo.py") is True


def test_matches_repo_pattern_leading_slash_anchors_to_root():
    assert _matches_repo_pattern("app/foo.py", "/app/foo.py") is True
    assert _matches_repo_pattern("other/app/foo.py", "/app/foo.py") is False


def test_matches_repo_pattern_slash_in_middle_anchors_without_leading_slash():
    # Any "/" in the pattern (other than a purely trailing one) makes the
    # match anchored to the start of the path, per CODEOWNERS/gitattributes
    # semantics implemented here.
    assert _matches_repo_pattern("app/foo.py", "app/*.py") is True
    assert _matches_repo_pattern("nested/app/foo.py", "app/*.py") is False


def test_matches_repo_pattern_single_star_does_not_cross_directory_boundary():
    assert _matches_repo_pattern("app/sub/foo.py", "app/*.py") is False


def test_matches_repo_pattern_double_star_crosses_directory_boundaries():
    assert _matches_repo_pattern("app/sub/deep/foo.py", "app/**") is True
    assert _matches_repo_pattern("app/sub/deep/foo.py", "/app/**") is True


def test_matches_repo_pattern_trailing_slash_implies_directory_wildcard():
    assert _matches_repo_pattern("app/foo.py", "app/") is True
    assert _matches_repo_pattern("app/sub/foo.py", "app/") is True
    assert _matches_repo_pattern("appendix/foo.py", "app/") is False


def test_matches_repo_pattern_question_mark_matches_single_non_slash_char():
    assert _matches_repo_pattern("app/foo.py", "?pp/foo.py") is True
    assert _matches_repo_pattern("a/pp/foo.py", "?pp/foo.py") is False


def test_matches_repo_pattern_empty_pattern_never_matches():
    assert _matches_repo_pattern("app/foo.py", "") is False


def test_matches_repo_pattern_whitespace_only_pattern_never_matches():
    assert _matches_repo_pattern("app/foo.py", "   ") is False


def test_matches_repo_pattern_normalizes_backslashes_in_pattern():
    assert _matches_repo_pattern("app/foo.py", "app\\foo.py") is True


def test_matches_repo_pattern_is_case_sensitive():
    assert _matches_repo_pattern("APP/foo.py", "app/foo.py") is False


def test_matches_repo_pattern_special_regex_characters_are_escaped():
    # "." in a glob pattern is literal, not "any character" - a pattern like
    # "app.py" must not match "appXpy" even though "." is a regex metachar.
    assert _matches_repo_pattern("appXpy", "app.py") is False
    assert _matches_repo_pattern("app.py", "app.py") is True


# --------------------------------------------------------------------------
# _matches_any_repo_pattern
# --------------------------------------------------------------------------


def test_matches_any_repo_pattern_true_when_one_pattern_matches():
    assert _matches_any_repo_pattern("app/foo.py", ["*.md", "*.py"]) is True


def test_matches_any_repo_pattern_false_when_none_match():
    assert _matches_any_repo_pattern("app/foo.py", ["*.md", "*.txt"]) is False


def test_matches_any_repo_pattern_empty_pattern_list_is_false():
    assert _matches_any_repo_pattern("app/foo.py", []) is False


# --------------------------------------------------------------------------
# _matches_ordered_patterns
# --------------------------------------------------------------------------


def test_matches_ordered_patterns_empty_pattern_list_is_not_included():
    assert _matches_ordered_patterns("app/foo.py", []) is False


def test_matches_ordered_patterns_simple_include():
    assert _matches_ordered_patterns("app/foo.py", ["app/**"]) is True
    assert _matches_ordered_patterns("web/foo.py", ["app/**"]) is False


def test_matches_ordered_patterns_negation_excludes_a_matched_file():
    patterns = ["app/**", "!app/generated/**"]
    assert _matches_ordered_patterns("app/generated/x.py", patterns) is False
    assert _matches_ordered_patterns("app/handwritten/x.py", patterns) is True


def test_matches_ordered_patterns_later_pattern_overrides_earlier_one():
    # Ordering matters: the last matching pattern in the list wins,
    # mirroring GitHub Actions' paths/paths-ignore evaluation order.
    reincluded = _matches_ordered_patterns("app/x.py", ["!app/**", "app/**"])
    assert reincluded is True

    excluded_last = _matches_ordered_patterns("app/x.py", ["app/**", "!app/**"])
    assert excluded_last is False


def test_matches_ordered_patterns_non_matching_negation_has_no_effect():
    patterns = ["app/**", "!web/**"]
    assert _matches_ordered_patterns("app/foo.py", patterns) is True


# --------------------------------------------------------------------------
# _is_safe_relative_path
# --------------------------------------------------------------------------


def test_is_safe_relative_path_accepts_ordinary_relative_path():
    assert _is_safe_relative_path("app/foo.py") is True


def test_is_safe_relative_path_rejects_absolute_path():
    assert _is_safe_relative_path("/etc/passwd") is False


def test_is_safe_relative_path_rejects_leading_parent_traversal():
    assert _is_safe_relative_path("../outside.py") is False


def test_is_safe_relative_path_rejects_embedded_parent_traversal():
    assert _is_safe_relative_path("app/../../etc/passwd") is False


def test_is_safe_relative_path_rejects_parent_traversal_at_the_end():
    assert _is_safe_relative_path("app/..") is False


def test_is_safe_relative_path_accepts_dot_current_directory_segment():
    # A literal "." segment is not a traversal risk; only ".." components
    # are rejected.
    assert _is_safe_relative_path("app/./foo.py") is True
    assert _is_safe_relative_path("./app/foo.py") is True


def test_is_safe_relative_path_accepts_filename_containing_dotdot_substring():
    # ".." must be an exact path *component*, not merely a substring of a
    # filename - "foo..py" or "..foo" are not traversal attempts.
    assert _is_safe_relative_path("app/foo..py") is True
    assert _is_safe_relative_path("app/..foo.py") is True
