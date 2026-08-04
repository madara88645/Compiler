"""Unit tests for app.pr_safety.path_rules batch helpers.

normalize_paths / list_test_files / list_source_files_needing_tests are pure,
deterministic, and used directly by app/pr_safety/analyzer.py and
app/pr_safety/repo_signals.py, but (unlike their singular/per-file siblings
in tests/test_pr_safety_path_rules.py) had no direct unit tests of their own.
"""

from __future__ import annotations

from app.pr_safety.path_rules import (
    list_source_files_needing_tests,
    list_test_files,
    normalize_paths,
)


# --------------------------------------------------------------------------
# normalize_paths
# --------------------------------------------------------------------------


def test_normalize_paths_converts_backslashes_and_strips_whitespace():
    assert normalize_paths([" a\\b.py ", "c/d.py"]) == ["a/b.py", "c/d.py"]


def test_normalize_paths_drops_empty_entries():
    assert normalize_paths(["", "   ", "app/compiler.py"]) == ["app/compiler.py"]


def test_normalize_paths_deduplicates_while_preserving_first_occurrence_order():
    assert normalize_paths(["b.py", "a.py", "b.py", "a.py"]) == ["b.py", "a.py"]


def test_normalize_paths_deduplicates_across_backslash_and_forward_slash_forms():
    assert normalize_paths(["a\\b.py", "a/b.py"]) == ["a/b.py"]


def test_normalize_paths_empty_input_returns_empty_list():
    assert normalize_paths([]) == []


# --------------------------------------------------------------------------
# list_test_files
# --------------------------------------------------------------------------


def test_list_test_files_filters_to_only_test_files():
    paths = ["app/compiler.py", "tests/test_compiler.py", "docs/README.md"]
    assert list_test_files(paths) == ["tests/test_compiler.py"]


def test_list_test_files_returns_empty_list_when_no_test_files_present():
    assert list_test_files(["app/compiler.py", "docs/README.md"]) == []


def test_list_test_files_normalizes_and_deduplicates_input():
    paths = ["tests\\test_foo.py", "tests/test_foo.py"]
    assert list_test_files(paths) == ["tests/test_foo.py"]


# --------------------------------------------------------------------------
# list_source_files_needing_tests
# --------------------------------------------------------------------------


def test_list_source_files_needing_tests_filters_to_only_source_files():
    paths = [
        "app/compiler.py",
        "tests/test_compiler.py",
        "docs/README.md",
        "config/settings.yaml",
    ]
    assert list_source_files_needing_tests(paths) == ["app/compiler.py"]


def test_list_source_files_needing_tests_excludes_test_doc_and_config_files():
    paths = ["tests/test_foo.py", "README.md", "app/config.yaml"]
    assert list_source_files_needing_tests(paths) == []


def test_list_source_files_needing_tests_empty_input_returns_empty_list():
    assert list_source_files_needing_tests([]) == []
