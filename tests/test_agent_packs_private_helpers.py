from __future__ import annotations

import pytest

from app.adapters.agent_packs import (
    _classify_kind,
    _media_type_for_path,
    _normalize_pack_path,
    _slugify,
    _tool_name_from_goal,
    _unique_lines,
)


class TestNormalizePackPath:
    def test_accepts_simple_relative_path(self):
        assert _normalize_pack_path("CLAUDE.md") == "CLAUDE.md"

    def test_accepts_nested_relative_path(self):
        assert _normalize_pack_path(".claude/agents/reviewer.md") == ".claude/agents/reviewer.md"

    def test_normalizes_backslashes_to_forward_slashes(self):
        assert _normalize_pack_path(".claude\\agents\\reviewer.md") == ".claude/agents/reviewer.md"

    def test_strips_surrounding_whitespace(self):
        assert _normalize_pack_path("  CLAUDE.md  ") == "CLAUDE.md"

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _normalize_pack_path("")

    def test_rejects_whitespace_only_path(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _normalize_pack_path("   ")

    def test_rejects_unix_absolute_path(self):
        with pytest.raises(ValueError, match="must be relative"):
            _normalize_pack_path("/etc/passwd")

    def test_rejects_windows_absolute_path(self):
        with pytest.raises(ValueError, match="must be relative"):
            _normalize_pack_path("C:/Windows/System32")

    def test_rejects_parent_traversal_segment(self):
        with pytest.raises(ValueError, match="unsafe segments"):
            _normalize_pack_path("../etc/passwd")

    def test_rejects_embedded_parent_traversal_segment(self):
        with pytest.raises(ValueError, match="unsafe segments"):
            _normalize_pack_path(".claude/../../etc/passwd")

    def test_rejects_current_dir_segment(self):
        with pytest.raises(ValueError, match="unsafe segments"):
            _normalize_pack_path("./CLAUDE.md")

    def test_rejects_double_slash_empty_segment(self):
        with pytest.raises(ValueError, match="unsafe segments"):
            _normalize_pack_path(".claude//agents/reviewer.md")

    def test_rejects_trailing_slash_empty_segment(self):
        with pytest.raises(ValueError, match="unsafe segments"):
            _normalize_pack_path(".claude/agents/")


class TestSlugify:
    def test_lowercases_and_hyphenates(self):
        assert _slugify("FastAPI Webhook Service") == "fastapi-webhook-service"

    def test_collapses_repeated_hyphens(self):
        assert _slugify("a---b") == "a-b"

    def test_strips_leading_and_trailing_hyphens(self):
        assert _slugify("--hello--") == "hello"

    def test_replaces_non_alphanumeric_with_hyphen(self):
        assert _slugify("a/b_c.d") == "a-b-c-d"

    def test_empty_string_falls_back_to_default(self):
        assert _slugify("") == "agent-pack"

    def test_all_symbols_falls_back_to_default(self):
        assert _slugify("!!!___...") == "agent-pack"

    def test_preserves_digits(self):
        assert _slugify("Python 3.12 Service") == "python-3-12-service"


class TestClassifyKind:
    def test_claude_md_exact_match(self):
        assert _classify_kind("CLAUDE.md") == "claude_md"

    def test_settings_json_suffix(self):
        assert _classify_kind(".claude/settings.json") == "settings"

    def test_agents_directory_segment(self):
        assert _classify_kind(".claude/agents/reviewer.md") == "agents"

    def test_mcp_server_py(self):
        assert _classify_kind("integrations/mcp-server/server.py") == "mcp"

    def test_mcp_case_insensitive_keyword(self):
        assert _classify_kind("scripts/MCP-bridge.py") == "mcp"

    def test_github_workflow_path(self):
        assert _classify_kind(".github/workflows/ci.yml") == "workflow"

    def test_yml_suffix_outside_workflows_dir(self):
        assert _classify_kind("config/policy.yml") == "workflow"

    def test_readme_suffix(self):
        assert _classify_kind("README.md") == "readme"

    def test_nested_readme_suffix(self):
        assert _classify_kind("docs/README.md") == "readme"

    def test_default_files_bucket(self):
        assert _classify_kind("src/index.ts") == "files"

    def test_normalizes_backslashes_before_classifying(self):
        assert _classify_kind(".claude\\agents\\reviewer.md") == "agents"


class TestMediaTypeForPath:
    def test_json(self):
        assert _media_type_for_path("settings.json") == "application/json"

    def test_markdown(self):
        assert _media_type_for_path("CLAUDE.md") == "text/markdown; charset=utf-8"

    def test_yml(self):
        assert _media_type_for_path("ci.yml") == "application/yaml"

    def test_yaml(self):
        assert _media_type_for_path("ci.yaml") == "application/yaml"

    def test_python(self):
        assert _media_type_for_path("server.py") == "text/x-python; charset=utf-8"

    def test_unknown_extension_falls_back_to_plain_text(self):
        assert _media_type_for_path("Dockerfile") == "text/plain; charset=utf-8"


class TestToolNameFromGoal:
    def test_extracts_meaningful_words(self):
        assert _tool_name_from_goal("Validate Stripe webhooks") == "validate_stripe_webhooks"

    def test_stops_at_and_clause(self):
        assert _tool_name_from_goal("Fetch orders and sync inventory") == "fetch_orders"

    def test_stops_at_period(self):
        assert _tool_name_from_goal("Review pull requests. Then merge them.") == "review_pull_requests"

    def test_filters_stop_words(self):
        assert _tool_name_from_goal("Search for a repository task") == "search_repository_task"

    def test_limits_to_four_words(self):
        assert _tool_name_from_goal("alpha beta gamma delta epsilon zeta") == "alpha_beta_gamma_delta"

    def test_empty_goal_falls_back_to_default(self):
        assert _tool_name_from_goal("") == "repository_task"

    def test_only_stop_words_falls_back_to_default(self):
        assert _tool_name_from_goal("a the to for") == "repository_task"


class TestUniqueLines:
    def test_deduplicates_case_insensitively(self):
        assert _unique_lines(["Hello World", "hello world", "HELLO WORLD"]) == ["Hello World"]

    def test_normalizes_internal_whitespace(self):
        assert _unique_lines(["a   b\tc"]) == ["a b c"]

    def test_drops_empty_and_whitespace_only_entries(self):
        assert _unique_lines(["", "   ", "keep"]) == ["keep"]

    def test_preserves_first_seen_order(self):
        assert _unique_lines(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]

    def test_handles_none_values_gracefully(self):
        assert _unique_lines([None, "keep", None]) == ["keep"]

    def test_empty_list_returns_empty_list(self):
        assert _unique_lines([]) == []
