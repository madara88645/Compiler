"""Direct unit tests for pure string-slugification helpers in
app.adapters.agent_packs: `_slugify` and `_build_download_name`.
"""

from __future__ import annotations

from app.adapters.agent_packs import AgentPackRequest, _build_download_name, _slugify


def _req(**overrides) -> AgentPackRequest:
    defaults = dict(
        project_type="My Project",
        stack="Python",
        goal="Do something useful",
        pack_type="project-pack",
    )
    defaults.update(overrides)
    return AgentPackRequest(**defaults)


class TestSlugify:
    def test_alnum_preserved_lowercased(self):
        assert _slugify("Hello World") == "hello-world"

    def test_non_alnum_becomes_hyphen(self):
        assert _slugify("Hello, World!") == "hello-world"

    def test_collapses_consecutive_hyphens(self):
        assert _slugify("a---b") == "a-b"

    def test_strips_leading_and_trailing_hyphens(self):
        assert _slugify("-abc-") == "abc"

    def test_empty_string_falls_back_to_agent_pack(self):
        assert _slugify("") == "agent-pack"

    def test_all_non_alnum_falls_back_to_agent_pack(self):
        assert _slugify("!!!") == "agent-pack"

    def test_digits_preserved(self):
        assert _slugify("Project 123") == "project-123"

    def test_mixed_separators_collapse_to_single_hyphen(self):
        assert _slugify("foo -- bar__baz") == "foo-bar-baz"


class TestBuildDownloadName:
    def test_basic_project_pack_name(self):
        req = _req(project_type="MyApp", pack_type="project-pack")
        assert _build_download_name(req) == "myapp-project-pack-claude"

    def test_special_characters_in_project_type_slugified(self):
        req = _req(project_type="My React App!", pack_type="subagent")
        assert _build_download_name(req) == "my-react-app-subagent-claude"

    def test_pr_reviewer_pack_type_included(self):
        req = _req(project_type="Repo", pack_type="pr-reviewer")
        assert _build_download_name(req) == "repo-pr-reviewer-claude"

    def test_mcp_tool_stub_pack_type_included(self):
        req = _req(project_type="Repo", pack_type="mcp-tool-stub")
        assert _build_download_name(req) == "repo-mcp-tool-stub-claude"
