"""Direct unit tests for app.pr_safety.path_rules.

tests/test_pr_safety.py only exercises these helpers indirectly through
analyze_pr_safety() end-to-end scenarios. This file pins the pure
classification/pattern-matching logic itself (path normalization, file-type
detection, risky-area rules, scope-term extraction) which has no dedicated
direct test coverage.
"""

from app.pr_safety.path_rules import (
    detect_risky_areas,
    extract_scope_terms,
    group_changed_files,
    is_config_file,
    is_doc_file,
    is_source_file,
    is_test_file,
    list_source_files_needing_tests,
    list_test_files,
    normalize_path,
    normalize_paths,
    path_reflects_scope_term,
    top_level_directories,
)


def test_normalize_path_converts_backslashes_and_strips_whitespace():
    assert normalize_path("  src\\utils\\file.py  ") == "src/utils/file.py"


def test_normalize_paths_dedupes_after_normalization():
    result = normalize_paths(["src\\a.py", "src/a.py", "src/b.py", ""])
    assert result == ["src/a.py", "src/b.py"]


def test_is_test_file_matches_python_and_js_conventions():
    assert is_test_file("tests/test_foo.py")
    assert is_test_file("src/foo_test.go")
    assert is_test_file("src/component.test.tsx")
    assert is_test_file("src/component.spec.js")
    assert not is_test_file("src/foo.py")


def test_is_doc_file_matches_extension_and_readme():
    assert is_doc_file("docs/guide.md")
    assert is_doc_file("README.md")
    assert is_doc_file("CHANGELOG.rst")
    assert not is_doc_file("src/app.py")


def test_is_config_file_matches_known_extensions():
    assert is_config_file("config/settings.yaml")
    assert is_config_file("pyproject.toml")
    assert not is_config_file("src/app.py")


def test_is_source_file_excludes_tests_docs_and_config():
    assert is_source_file("src/app.py")
    assert not is_source_file("tests/test_app.py")
    assert not is_source_file("README.md")
    assert not is_source_file("config.yaml")
    assert not is_source_file("no_extension")


def test_group_changed_files_buckets_by_category():
    groups = group_changed_files(
        [
            "src/app.py",
            "tests/test_app.py",
            "README.md",
            ".github/workflows/ci.yml",
            "auth/login.py",
            ".env.production",
            "unclassified_binary.bin",
        ]
    )
    assert groups["source"] == ["src/app.py"]
    assert groups["tests"] == ["tests/test_app.py"]
    assert groups["docs"] == ["README.md"]
    assert groups["ci"] == [".github/workflows/ci.yml"]
    assert groups["auth"] == ["auth/login.py"]
    assert groups["secrets"] == [".env.production"]
    assert groups["other"] == ["unclassified_binary.bin"]


def test_group_changed_files_omits_empty_groups():
    groups = group_changed_files(["src/app.py"])
    assert list(groups.keys()) == ["source"]


def test_group_changed_files_assigns_each_path_to_exactly_one_group():
    paths = ["auth/session.py", "migrations/0001_init.py"]
    groups = group_changed_files(paths)
    assert groups["auth"] == ["auth/session.py"]
    assert groups["migrations"] == ["migrations/0001_init.py"]


def test_detect_risky_areas_flags_auth_and_secrets():
    hits = detect_risky_areas(["auth/login.py", ".env", "src/app.py"])
    categories = {category for category, _path, _reason in hits}
    assert categories == {"auth", "secrets"}


def test_detect_risky_areas_deduplicates_same_category_and_path():
    hits = detect_risky_areas(["auth/login.py", "auth/login.py"])
    assert len(hits) == 1


def test_detect_risky_areas_empty_for_ordinary_paths():
    assert detect_risky_areas(["src/app.py", "README.md"]) == []


def test_list_test_files_filters_to_test_paths():
    assert list_test_files(["tests/test_a.py", "src/b.py"]) == ["tests/test_a.py"]


def test_list_source_files_needing_tests_excludes_non_source():
    result = list_source_files_needing_tests(
        ["src/a.py", "tests/test_a.py", "README.md", "config.yaml"]
    )
    assert result == ["src/a.py"]


def test_top_level_directories_collects_unique_roots_sorted():
    result = top_level_directories(["src/a.py", "src/b.py", "tests/test_a.py", "README.md"])
    assert result == ["README.md", "src", "tests"]


def test_extract_scope_terms_strips_stopwords_and_short_tokens():
    terms = extract_scope_terms("Fix the login bug", "This change updates the auth flow")
    assert "login" in terms
    assert "auth" in terms
    assert "the" not in terms
    assert "fix" not in terms


def test_extract_scope_terms_includes_focus_terms_present_in_text():
    terms = extract_scope_terms("Add payment webhook", "")
    assert "payment" in terms


def test_extract_scope_terms_dedupes_repeated_tokens():
    terms = extract_scope_terms("auth auth auth", "")
    assert terms.count("auth") == 1


def test_path_reflects_scope_term_matches_substring_in_path():
    assert path_reflects_scope_term("src/auth/login.py", "auth")


def test_path_reflects_scope_term_matches_normalized_filename_stem():
    assert path_reflects_scope_term("src/user_login.py", "login")


def test_path_reflects_scope_term_false_when_absent():
    assert not path_reflects_scope_term("src/app.py", "payment")
