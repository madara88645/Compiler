"""
Gap-coverage tests for currently-untested, pure, deterministic module-level
helpers in app/adapters/agent_ir.py and app/adapters/agent_packs.py.

Covers:
- agent_ir._parse_sections
- agent_ir._map_sections
- agent_packs._build_agent_brief
- agent_packs._build_skill_brief
- agent_packs._validation_workflow
- agent_packs._agent_output_is_usable
- agent_packs._skill_output_is_usable
"""

from __future__ import annotations

from app.adapters.agent_ir import AgentExportIR, _map_sections, _parse_sections
from app.adapters.agent_packs import (
    AgentPackRequest,
    _agent_output_is_usable,
    _build_agent_brief,
    _build_skill_brief,
    _skill_output_is_usable,
    _validation_workflow,
)
from app.adapters.skill_ir import SkillExportIR


# ---------------------------------------------------------------------------
# agent_ir._parse_sections
# ---------------------------------------------------------------------------


class TestParseSections:
    def test_empty_markdown_returns_empty_dict(self):
        assert _parse_sections("") == {}

    def test_single_section_basic(self):
        text = "## Role\nYou are an assistant.\n"
        assert _parse_sections(text) == {"role": "You are an assistant."}

    def test_multiple_sections_are_all_captured(self):
        text = "## Role\nDo X.\n\n## Goals\n- goal one\n- goal two\n"
        sections = _parse_sections(text)
        assert sections["role"] == "Do X."
        assert sections["goals"] == "- goal one\n- goal two"

    def test_duplicate_headers_last_one_wins(self):
        # _parse_sections uses a plain dict keyed by lowercased header text, so a
        # second occurrence of the same header overwrites the first's content.
        text = "## Role\nFirst role text\n\n## Role\nSecond role text\n"
        sections = _parse_sections(text)
        assert sections == {"role": "Second role text"}

    def test_unrecognized_header_is_kept_verbatim_as_key(self):
        # _parse_sections does not filter/alias headers -- that's _map_sections' job.
        text = "## Totally Made Up Header\nSome content here.\n"
        sections = _parse_sections(text)
        assert sections == {"totally made up header": "Some content here."}

    def test_header_keys_are_lowercased(self):
        text = "## RoLe\nMixed case header.\n"
        sections = _parse_sections(text)
        assert "role" in sections
        assert sections["role"] == "Mixed case header."

    def test_top_level_heading_closes_pending_section(self):
        # A bare "# " (not "## ") heading flushes and clears the current section,
        # so content after it (until the next "## ") is dropped.
        text = "## Role\nRole content\n# Some Title\nOrphaned text, not attached to any section\n"
        sections = _parse_sections(text)
        assert sections == {"role": "Role content"}

    def test_top_level_heading_before_any_section_is_a_no_op(self):
        text = "# Agent Name\nIntro text with no section yet.\n## Role\nActual role.\n"
        sections = _parse_sections(text)
        assert sections == {"role": "Actual role."}

    def test_content_before_first_section_is_discarded(self):
        text = "Some preamble that isn't inside any section.\n## Goals\n- one goal\n"
        sections = _parse_sections(text)
        assert sections == {"goals": "- one goal"}

    def test_trailing_section_without_following_header_is_still_captured(self):
        # Covers the final flush after the loop ends (current_key still set).
        text = "## Constraints\n- never do X\n- never do Y"
        sections = _parse_sections(text)
        assert sections == {"constraints": "- never do X\n- never do Y"}

    def test_malformed_mixed_h1_h2_headers_only_h2_becomes_a_section(self):
        text = (
            "# Title One\n"
            "## Role\n"
            "role body\n"
            "# Title Two\n"
            "### Not a section (h3, ignored as body-ish but no active section)\n"
            "## Goals\n"
            "- goal body\n"
        )
        sections = _parse_sections(text)
        assert sections == {"role": "role body", "goals": "- goal body"}


# ---------------------------------------------------------------------------
# agent_ir._map_sections
# ---------------------------------------------------------------------------


class TestMapSections:
    def test_empty_sections_returns_empty_dict(self):
        assert _map_sections({}) == {}

    def test_recognized_aliases_map_to_canonical_keys(self):
        sections = {
            "persona": "You are helpful.",
            "objective": "Ship the feature.",
            "rule": "No secrets in logs.",
            "steps": "Do step 1.",
            "tools & capabilities": "Bash, Read",
        }
        mapped = _map_sections(sections)
        assert mapped == {
            "role": "You are helpful.",
            "goals": "Ship the feature.",
            "constraints": "No secrets in logs.",
            "workflows": "Do step 1.",
            "tech_stack": "Bash, Read",
        }

    def test_unrecognized_header_is_dropped(self):
        sections = {"role": "Assistant", "random unknown header": "irrelevant"}
        mapped = _map_sections(sections)
        assert mapped == {"role": "Assistant"}
        assert "random unknown header" not in mapped

    def test_first_alias_for_a_canonical_key_wins_over_later_ones(self):
        # Iteration order of a dict follows insertion order in Python; the first
        # alias whose canonical target isn't already mapped is kept.
        sections = {"goal": "First goal text", "objectives": "Second goal text"}
        mapped = _map_sections(sections)
        assert mapped == {"goals": "First goal text"}

    def test_multiple_distinct_aliases_all_map_independently(self):
        sections = {
            "goals": "goal text",
            "goal": "should be dropped, goals already mapped",
            "constraints": "constraint text",
        }
        mapped = _map_sections(sections)
        assert mapped == {"goals": "goal text", "constraints": "constraint text"}

    def test_all_unrecognized_headers_yield_empty_mapping(self):
        sections = {"foo": "bar", "baz": "qux"}
        assert _map_sections(sections) == {}


# ---------------------------------------------------------------------------
# agent_packs._build_agent_brief
# ---------------------------------------------------------------------------


def _agent_pack_request(**overrides) -> AgentPackRequest:
    defaults = dict(
        project_type="Billing service",
        stack="Python, FastAPI",
        goal="Validate webhook signatures",
        pack_type="project-pack",
        risk_mode="balanced",
    )
    defaults.update(overrides)
    return AgentPackRequest(**defaults)


class TestBuildAgentBrief:
    def test_balanced_risk_mode_uses_usability_line(self):
        req = _agent_pack_request(risk_mode="balanced")
        brief = _build_agent_brief(req)
        assert "Balance usability with strong default safeguards" in brief
        assert "Use strict security defaults" not in brief

    def test_strict_risk_mode_uses_strict_security_line(self):
        req = _agent_pack_request(risk_mode="strict")
        brief = _build_agent_brief(req)
        assert "Use strict security defaults" in brief
        assert "Balance usability with strong default safeguards" not in brief

    def test_includes_project_type_stack_and_goal(self):
        req = _agent_pack_request(
            project_type="Widget API", stack="Go", goal="Add rate limiting"
        )
        brief = _build_agent_brief(req)
        assert "Widget API" in brief
        assert "Go" in brief
        assert "Add rate limiting" in brief

    def test_detected_stack_overrides_declared_stack(self):
        req = _agent_pack_request(stack="Node.js", detected_stack="Rust, Actix")
        brief = _build_agent_brief(req)
        assert "Rust, Actix" in brief
        assert "Node.js" not in brief

    def test_pr_reviewer_pack_type_adds_review_line(self):
        req = _agent_pack_request(pack_type="pr-reviewer")
        brief = _build_agent_brief(req)
        assert "review pull requests" in brief.lower()
        assert "prompt leakage" in brief

    def test_non_pr_reviewer_pack_type_has_no_review_line(self):
        req = _agent_pack_request(pack_type="subagent")
        brief = _build_agent_brief(req)
        assert "prompt leakage" not in brief

    def test_all_pack_type_labels_are_used(self):
        for pack_type, label_fragment in [
            ("project-pack", "full project pack"),
            ("subagent", "focused Claude subagent"),
            ("pr-reviewer", "PR reviewer pack"),
            ("mcp-tool-stub", "MCP tool stub"),
        ]:
            req = _agent_pack_request(pack_type=pack_type)
            brief = _build_agent_brief(req)
            assert label_fragment in brief


# ---------------------------------------------------------------------------
# agent_packs._build_skill_brief
# ---------------------------------------------------------------------------


class TestBuildSkillBrief:
    def test_strict_risk_mode_favors_validation_language(self):
        req = _agent_pack_request(risk_mode="strict")
        brief = _build_skill_brief(req)
        assert "strict validation" in brief
        assert "clean developer ergonomics" not in brief

    def test_balanced_risk_mode_favors_ergonomics_language(self):
        req = _agent_pack_request(risk_mode="balanced")
        brief = _build_skill_brief(req)
        assert "clean developer ergonomics" in brief
        assert "strict validation" not in brief

    def test_includes_project_type_stack_and_goal(self):
        req = _agent_pack_request(
            project_type="Inventory sync", stack="Node, Postgres", goal="Sync stock levels"
        )
        brief = _build_skill_brief(req)
        assert "Inventory sync" in brief
        assert "Node, Postgres" in brief
        assert "Sync stock levels" in brief

    def test_uses_declared_stack_not_detected_stack(self):
        # Unlike _build_agent_brief, _build_skill_brief always reads req.stack directly.
        req = _agent_pack_request(stack="Ruby", detected_stack="Elixir")
        brief = _build_skill_brief(req)
        assert "Ruby" in brief
        assert "Elixir" not in brief

    def test_mentions_mcp_tool_skill_definition(self):
        req = _agent_pack_request()
        brief = _build_skill_brief(req)
        assert "MCP tool skill definition" in brief


# ---------------------------------------------------------------------------
# agent_packs._validation_workflow
# ---------------------------------------------------------------------------


class TestValidationWorkflow:
    def test_no_detected_commands_uses_discovery_language(self):
        req = _agent_pack_request(detected_commands=None)
        workflow = _validation_workflow(req)
        assert "Discover the repository's existing validation commands" in workflow

    def test_empty_detected_commands_dict_also_uses_discovery_language(self):
        req = _agent_pack_request(detected_commands={})
        workflow = _validation_workflow(req)
        assert "Discover the repository's existing validation commands" in workflow

    def test_detected_commands_are_rendered_as_backtick_pairs(self):
        req = _agent_pack_request(
            detected_commands={"test": "pytest -q", "lint": "ruff check ."}
        )
        workflow = _validation_workflow(req)
        assert "test: `pytest -q`" in workflow
        assert "lint: `ruff check .`" in workflow
        assert "Run the repository's real validation commands" in workflow
        assert "Discover the repository's existing validation commands" not in workflow

    def test_result_always_mentions_shared_reporting_contract(self):
        for detected in (None, {}, {"build": "make build"}):
            req = _agent_pack_request(detected_commands=detected)
            workflow = _validation_workflow(req)
            assert "report commands, results, remaining risk, and files changed" in workflow


# ---------------------------------------------------------------------------
# agent_packs._agent_output_is_usable
# ---------------------------------------------------------------------------


class TestAgentOutputIsUsable:
    def test_empty_markdown_is_unusable(self):
        ir = AgentExportIR(name="Some Agent", role="does things")
        assert _agent_output_is_usable(ir, "") is False

    def test_whitespace_only_markdown_is_unusable(self):
        ir = AgentExportIR(name="Some Agent", role="does things")
        assert _agent_output_is_usable(ir, "   \n\t  ") is False

    def test_failure_marker_text_is_unusable(self):
        ir = AgentExportIR(name="Some Agent", role="does things")
        markdown = "# Error\n\nFailed to generate agent: something broke."
        assert _agent_output_is_usable(ir, markdown) is False

    def test_missing_api_key_marker_is_unusable(self):
        ir = AgentExportIR(name="Some Agent", role="does things")
        markdown = "API key is missing. Please configure OPENROUTER_API_KEY."
        assert _agent_output_is_usable(ir, markdown) is False

    def test_name_error_is_unusable_even_with_good_markdown(self):
        # Name "error" always fails regardless of other populated content.
        ir = AgentExportIR(name="Error", role="does things")
        assert _agent_output_is_usable(ir, "## Role\nreal role content") is False

    def test_default_placeholder_name_ai_agent_is_unusable(self):
        ir = AgentExportIR(name="AI Agent", role="does things")
        assert _agent_output_is_usable(ir, "## Role\nreal role content") is False

    def test_no_populated_fields_is_unusable(self):
        ir = AgentExportIR(name="Custom Name")  # role/goals/constraints/workflows all empty
        assert _agent_output_is_usable(ir, "## Something\nsome content") is False

    def test_role_present_makes_it_usable(self):
        ir = AgentExportIR(name="Custom Name", role="You review pull requests.")
        assert _agent_output_is_usable(ir, "## Role\nYou review pull requests.") is True

    def test_goals_present_without_role_still_usable(self):
        ir = AgentExportIR(name="Custom Name", goals=["Ship the feature"])
        assert _agent_output_is_usable(ir, "## Goals\n- Ship the feature") is True

    def test_case_insensitive_failure_marker_detection(self):
        ir = AgentExportIR(name="Custom Name", role="ok")
        assert _agent_output_is_usable(ir, "FAILED TO GENERATE agent output") is False


# ---------------------------------------------------------------------------
# agent_packs._skill_output_is_usable
# ---------------------------------------------------------------------------


class TestSkillOutputIsUsable:
    def test_empty_markdown_is_unusable(self):
        ir = SkillExportIR(name="my_skill", purpose="Does a thing")
        assert _skill_output_is_usable(ir, "") is False

    def test_whitespace_only_markdown_is_unusable(self):
        ir = SkillExportIR(name="my_skill", purpose="Does a thing")
        assert _skill_output_is_usable(ir, "\n  \n") is False

    def test_failure_marker_text_is_unusable(self):
        ir = SkillExportIR(name="my_skill", purpose="Does a thing")
        markdown = "# Error\n\nFailed to generate skill definition."
        assert _skill_output_is_usable(ir, markdown) is False

    def test_missing_api_key_marker_is_unusable(self):
        ir = SkillExportIR(name="my_skill", purpose="Does a thing")
        markdown = "Error: API key is missing."
        assert _skill_output_is_usable(ir, markdown) is False

    def test_name_error_is_unusable(self):
        ir = SkillExportIR(name="error", purpose="Does a thing")
        assert _skill_output_is_usable(ir, "## Purpose\nDoes a thing") is False

    def test_default_placeholder_name_skill_name_is_unusable(self):
        ir = SkillExportIR(name="skill_name", purpose="Does a thing")
        assert _skill_output_is_usable(ir, "## Purpose\nDoes a thing") is False

    def test_no_populated_fields_is_unusable(self):
        ir = SkillExportIR(name="custom_tool")  # purpose/params/implementation all empty
        assert _skill_output_is_usable(ir, "## Something\nsome content") is False

    def test_purpose_present_makes_it_usable(self):
        ir = SkillExportIR(name="custom_tool", purpose="Validates webhook signatures.")
        assert _skill_output_is_usable(ir, "## Purpose\nValidates webhook signatures.") is True

    def test_params_present_without_purpose_still_usable(self):
        from app.adapters.skill_ir import SkillParam

        ir = SkillExportIR(
            name="custom_tool",
            params=[SkillParam(name="request", type="str", description="the request")],
        )
        assert _skill_output_is_usable(ir, "## Input Schema\n- request: str") is True

    def test_implementation_present_without_purpose_or_params_still_usable(self):
        ir = SkillExportIR(name="custom_tool", implementation="Call the API and return JSON.")
        assert _skill_output_is_usable(ir, "## Implementation\nCall the API and return JSON.") is True
