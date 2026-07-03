from app.pr_safety.path_rules import (
    normalize_path,
    is_test_file,
    is_doc_file,
    is_config_file,
    is_source_file,
    group_changed_files,
    detect_risky_areas,
    extract_scope_terms,
    path_reflects_scope_term,
)


# --------------------------------------------------------------------------
# normalize_path
# --------------------------------------------------------------------------


def test_normalize_path_strips_whitespace_and_converts_backslashes():
    assert normalize_path("  a\\b\\c.py  ") == "a/b/c.py"


def test_normalize_path_leaves_forward_slash_path_unchanged():
    assert normalize_path("app/compiler.py") == "app/compiler.py"


def test_normalize_path_empty_string():
    assert normalize_path("   ") == ""


# --------------------------------------------------------------------------
# is_test_file
# --------------------------------------------------------------------------


def test_is_test_file_top_level_tests_dir():
    assert is_test_file("tests/test_foo.py") is True


def test_is_test_file_test_prefix_py():
    assert is_test_file("test_foo.py") is True


def test_is_test_file_test_suffix_py():
    assert is_test_file("foo_test.py") is True


def test_is_test_file_nested_dunder_tests_dir():
    assert is_test_file("web/app/components/__tests__/ReadinessBanner.spec.tsx") is True


def test_is_test_file_dot_test_ts():
    assert is_test_file("src/foo.test.ts") is True


def test_is_test_file_regular_source_is_not_a_test():
    assert is_test_file("app/foo.py") is False


def test_is_test_file_normalizes_backslashes():
    assert is_test_file("tests\\test_foo.py") is True


# --------------------------------------------------------------------------
# is_doc_file
# --------------------------------------------------------------------------


def test_is_doc_file_docs_directory():
    assert is_doc_file("docs/README.md") is True


def test_is_doc_file_readme_at_root():
    assert is_doc_file("README.md") is True


def test_is_doc_file_changelog_at_root():
    assert is_doc_file("CHANGELOG.md") is True


def test_is_doc_file_txt_extension():
    assert is_doc_file("notes.txt") is True


def test_is_doc_file_rst_extension():
    assert is_doc_file("docs/api.rst") is True


def test_is_doc_file_source_file_is_not_doc():
    assert is_doc_file("app/compiler.py") is False


def test_is_doc_file_no_extension_not_matched_by_pattern():
    assert is_doc_file("app/Makefile") is False


# --------------------------------------------------------------------------
# is_config_file
# --------------------------------------------------------------------------


def test_is_config_file_yaml_extension():
    assert is_config_file("app/config.yaml") is True


def test_is_config_file_config_directory():
    assert is_config_file("config/settings.json") is True


def test_is_config_file_json_at_root():
    assert is_config_file("package.json") is True


def test_is_config_file_toml_extension():
    assert is_config_file("pyproject.toml") is True


def test_is_config_file_source_file_is_not_config():
    assert is_config_file("app/compiler.py") is False


# --------------------------------------------------------------------------
# is_source_file
# --------------------------------------------------------------------------


def test_is_source_file_python_module():
    assert is_source_file("app/compiler.py") is True


def test_is_source_file_excludes_test_files():
    assert is_source_file("tests/test_foo.py") is False


def test_is_source_file_excludes_doc_files():
    assert is_source_file("docs/README.md") is False


def test_is_source_file_excludes_config_files():
    assert is_source_file("app/config.yaml") is False


def test_is_source_file_excludes_unknown_extensions():
    assert is_source_file("image.png") is False


def test_is_source_file_typescript():
    assert is_source_file("web/app/page.tsx") is True


# --------------------------------------------------------------------------
# group_changed_files
# --------------------------------------------------------------------------


def test_group_changed_files_buckets_by_category():
    paths = [
        "app/compiler.py",
        "tests/test_compiler.py",
        "docs/architecture.md",
        "config/settings.yaml",
        ".github/workflows/ci.yml",
        "api/routes/auth.py",
        ".env.example",
        "image.png",
    ]

    groups = group_changed_files(paths)

    assert groups == {
        "source": ["app/compiler.py"],
        "tests": ["tests/test_compiler.py"],
        "docs": ["docs/architecture.md"],
        "config": ["config/settings.yaml"],
        "ci": [".github/workflows/ci.yml"],
        "auth": ["api/routes/auth.py"],
        "secrets": [".env.example"],
        "other": ["image.png"],
    }


def test_group_changed_files_omits_empty_groups():
    groups = group_changed_files(["app/compiler.py"])
    assert set(groups.keys()) == {"source"}


def test_group_changed_files_deduplicates_and_normalizes_input():
    groups = group_changed_files(["app\\compiler.py", "app/compiler.py"])
    assert groups == {"source": ["app/compiler.py"]}


def test_group_changed_files_empty_input_returns_empty_dict():
    assert group_changed_files([]) == {}


def test_group_changed_files_a_path_only_belongs_to_one_group():
    # auth.py under api/routes matches both the "auth" GROUP_RULES pattern
    # and could be considered source; GROUP_RULES is checked first and wins.
    groups = group_changed_files(["api/routes/auth.py"])
    assert groups == {"auth": ["api/routes/auth.py"]}


# --------------------------------------------------------------------------
# detect_risky_areas
# --------------------------------------------------------------------------


def test_detect_risky_areas_finds_auth_and_api_hits_for_same_path():
    hits = detect_risky_areas(["api/routes/auth.py"])
    categories = {h[0] for h in hits}
    assert categories == {"auth", "api"}
    assert all(h[1] == "api/routes/auth.py" for h in hits)


def test_detect_risky_areas_secrets():
    hits = detect_risky_areas([".env.example"])
    assert hits == [
        ("secrets", ".env.example", "Touches secret or environment configuration")
    ]


def test_detect_risky_areas_migrations():
    hits = detect_risky_areas(["app/models/migrations/0001.py"])
    assert hits == [
        (
            "migrations",
            "app/models/migrations/0001.py",
            "Touches database migration files",
        )
    ]


def test_detect_risky_areas_no_hits_for_plain_source_file():
    assert detect_risky_areas(["app/emitters.py"]) == []


def test_detect_risky_areas_deduplicates_same_category_and_path():
    # "*auth*" would otherwise match multiple times if patterns overlapped;
    # verify duplicate input paths don't produce duplicate hits.
    hits = detect_risky_areas(["api/routes/auth.py", "api/routes/auth.py"])
    auth_hits = [h for h in hits if h[0] == "auth"]
    assert len(auth_hits) == 1


def test_detect_risky_areas_ci_workflow():
    hits = detect_risky_areas([".github/workflows/ci.yml"])
    assert ("ci", ".github/workflows/ci.yml", "Touches CI/CD workflow configuration") in hits


# --------------------------------------------------------------------------
# extract_scope_terms
# --------------------------------------------------------------------------


def test_extract_scope_terms_from_title_and_description():
    terms = extract_scope_terms(
        "feat: add login flow",
        "Add session-based login endpoints for the API.",
    )

    assert terms == [
        "login",
        "flow",
        "session-based",
        "endpoints",
        "api",
        "session",
        "endpoint",
    ]


def test_extract_scope_terms_drops_stop_words_and_short_tokens():
    terms = extract_scope_terms("fix: update the docs", "Make this change for readability.")
    for stop in ("fix", "update", "the", "make", "this", "for"):
        assert stop not in terms


def test_extract_scope_terms_dedupes_repeated_tokens():
    terms = extract_scope_terms("auth auth auth", "")
    assert terms.count("auth") == 1


def test_extract_scope_terms_empty_input_returns_empty_list():
    assert extract_scope_terms("", "") == []


# --------------------------------------------------------------------------
# path_reflects_scope_term
# --------------------------------------------------------------------------


def test_path_reflects_scope_term_direct_substring_match():
    assert path_reflects_scope_term("api/routes/auth.py", "auth") is True


def test_path_reflects_scope_term_no_match():
    assert path_reflects_scope_term("docs/CONTRIBUTING.md", "login") is False


def test_path_reflects_scope_term_matches_via_underscored_stem():
    # "session manager" isn't a literal substring of the path (underscore vs
    # space), but the stem-normalization step (underscores/hyphens -> spaces)
    # should still surface the match.
    assert path_reflects_scope_term("app/session_manager.py", "session manager") is True


def test_path_reflects_scope_term_matches_via_hyphenated_stem():
    assert path_reflects_scope_term("app/user-auth-flow.py", "auth flow") is True


def test_path_reflects_scope_term_case_insensitive():
    assert path_reflects_scope_term("API/Routes/Auth.py", "auth") is True
