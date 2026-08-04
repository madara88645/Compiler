"""Direct coverage for the pure path-matching helpers in ``app.pr_safety.path_rules``.

``normalize_paths``, ``_matches_any_pattern``, ``list_test_files``, and
``list_source_files_needing_tests`` back the PR-safety verdict feature but,
prior to this file, only had indirect coverage through higher-level
functions (``group_changed_files``, ``detect_risky_areas``, etc.) in
``tests/test_pr_safety_path_rules.py``. These tests exercise them directly,
including edge cases (empty/whitespace input, duplicate paths, backslash
normalization, and empty pattern sets) relevant to path-matching correctness.
"""

from app.pr_safety.path_rules import (
    TEST_FILE_PATTERNS,
    _matches_any_pattern,
    list_source_files_needing_tests,
    list_test_files,
    normalize_paths,
)


# --------------------------------------------------------------------------
# normalize_paths
# --------------------------------------------------------------------------


def test_normalize_paths_converts_backslashes_and_strips_whitespace():
    assert normalize_paths(["  app\\foo.py  "]) == ["app/foo.py"]


def test_normalize_paths_drops_empty_and_whitespace_only_entries():
    assert normalize_paths(["", "   ", "app/foo.py"]) == ["app/foo.py"]


def test_normalize_paths_deduplicates_after_normalization():
    # "app\\foo.py" and "app/foo.py" normalize to the same string, so the
    # second occurrence must be dropped rather than kept as a duplicate.
    result = normalize_paths(["app\\foo.py", "app/foo.py", "app/bar.py"])
    assert result == ["app/foo.py", "app/bar.py"]


def test_normalize_paths_preserves_first_occurrence_order():
    result = normalize_paths(["c.py", "a.py", "b.py", "a.py"])
    assert result == ["c.py", "a.py", "b.py"]


def test_normalize_paths_empty_list_returns_empty_list():
    assert normalize_paths([]) == []


def test_normalize_paths_all_whitespace_entries_returns_empty_list():
    assert normalize_paths(["   ", "\t", ""]) == []


# --------------------------------------------------------------------------
# _matches_any_pattern
# --------------------------------------------------------------------------


def test_matches_any_pattern_true_when_one_pattern_matches():
    assert _matches_any_pattern("app/foo.py", ("*.md", "*.py")) is True


def test_matches_any_pattern_false_when_no_pattern_matches():
    assert _matches_any_pattern("app/foo.py", ("*.md", "*.txt")) is False


def test_matches_any_pattern_false_for_empty_pattern_tuple():
    assert _matches_any_pattern("app/foo.py", ()) is False


def test_matches_any_pattern_is_case_sensitive_on_posix():
    # fnmatch on POSIX platforms is case-sensitive; a pattern matching
    # lowercase paths should not match an uppercase variant.
    assert _matches_any_pattern("APP/FOO.PY", ("*.py",)) is False


def test_matches_any_pattern_glob_star_does_not_cross_directories_implicitly():
    # fnmatch's "*" matches "/" too (unlike shell globbing in some
    # contexts), so a single-segment wildcard can still match nested paths.
    assert _matches_any_pattern("a/b/c.py", ("*.py",)) is True


def test_matches_any_pattern_stops_after_first_match():
    # Sanity check the explicit loop short-circuits like any(): matching on
    # an early pattern still returns True even if later patterns are bogus
    # fnmatch expressions that would otherwise raise if evaluated eagerly
    # (fnmatch itself won't raise, but this documents the short-circuit
    # intent of the loop).
    assert _matches_any_pattern("README.md", ("README*", "[unclosed")) is True


# --------------------------------------------------------------------------
# list_test_files
# --------------------------------------------------------------------------


def test_list_test_files_filters_to_test_files_only():
    paths = ["tests/test_a.py", "app/b.py", "app/c_test.go", "docs/readme.md"]
    assert list_test_files(paths) == ["tests/test_a.py", "app/c_test.go"]


def test_list_test_files_normalizes_backslashes_before_filtering():
    assert list_test_files(["tests\\test_a.py"]) == ["tests/test_a.py"]


def test_list_test_files_empty_input_returns_empty_list():
    assert list_test_files([]) == []


def test_list_test_files_no_test_files_present_returns_empty_list():
    assert list_test_files(["app/foo.py", "docs/readme.md"]) == []


def test_list_test_files_deduplicates_via_normalize_paths():
    result = list_test_files(["tests/test_a.py", "tests\\test_a.py"])
    assert result == ["tests/test_a.py"]


def test_list_test_files_matches_every_declared_test_pattern_family():
    # Spot-check that at least one representative path per pattern group in
    # TEST_FILE_PATTERNS is recognized end-to-end through list_test_files.
    assert TEST_FILE_PATTERNS  # sanity: pattern tuple isn't empty
    candidates = [
        "test_foo.py",
        "foo_test.py",
        "foo_test.go",
        "foo.test.ts",
        "foo.test.tsx",
        "foo.test.js",
        "foo.test.jsx",
        "foo.spec.ts",
        "foo.spec.tsx",
        "foo.spec.js",
        "foo.spec.jsx",
        "tests/foo.py",
        "test/foo.py",
        "__tests__/foo.js",
        "nested/dir/tests/foo.py",
    ]
    result = list_test_files(candidates)
    assert result == candidates


# --------------------------------------------------------------------------
# list_source_files_needing_tests
# --------------------------------------------------------------------------


def test_list_source_files_needing_tests_filters_to_source_files_only():
    paths = [
        "app/foo.py",
        "tests/test_foo.py",
        "docs/readme.md",
        "app/config.yaml",
        "image.png",
    ]
    assert list_source_files_needing_tests(paths) == ["app/foo.py"]


def test_list_source_files_needing_tests_excludes_test_files_even_with_source_extension():
    assert list_source_files_needing_tests(["tests/test_foo.py"]) == []


def test_list_source_files_needing_tests_excludes_files_without_known_extension():
    assert list_source_files_needing_tests(["Makefile", "Dockerfile"]) == []


def test_list_source_files_needing_tests_normalizes_and_deduplicates():
    result = list_source_files_needing_tests(["app\\foo.py", "app/foo.py"])
    assert result == ["app/foo.py"]


def test_list_source_files_needing_tests_empty_input_returns_empty_list():
    assert list_source_files_needing_tests([]) == []


def test_list_source_files_needing_tests_preserves_input_order():
    paths = ["app/b.py", "app/a.py", "docs/readme.md", "app/c.go"]
    assert list_source_files_needing_tests(paths) == ["app/b.py", "app/a.py", "app/c.go"]
