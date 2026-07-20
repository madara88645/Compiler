"""Unit tests for the LLM-output trust gates in app/adapters/agent_packs.py.

`_agent_output_is_usable` and `_skill_output_is_usable` decide whether
LLM-generated markdown is trusted (and thus surfaced to the user) or
discarded in favor of the request-grounded IR fallback. Getting this wrong
means either hallucinated content is trusted, or good content is thrown
away.

Both functions share the same shape of gate:
1. Reject empty/whitespace-only markdown.
2. Reject markdown containing known failure/error markers.
3. Reject a handful of known placeholder/error names.
4. Otherwise require at least one populated "real content" field on the IR.
"""

from __future__ import annotations

from app.adapters.agent_packs import (
    _agent_output_is_usable,
    _skill_output_is_usable,
)
from app.adapters.agent_ir import AgentExportIR
from app.adapters.skill_ir import SkillExportIR


# ---------------------------------------------------------------------------
# _agent_output_is_usable
# ---------------------------------------------------------------------------


class TestAgentOutputIsUsable:
    def test_usable_when_markdown_present_and_ir_has_role(self):
        ir = AgentExportIR(name="Repo Maintainer", role="Maintains the repository")
        assert _agent_output_is_usable(ir, "# Repo Maintainer\n\nSome content") is True

    def test_usable_when_ir_has_only_goals(self):
        ir = AgentExportIR(name="Focused Agent", goals=["ship the feature"])
        assert _agent_output_is_usable(ir, "some markdown") is True

    def test_usable_when_ir_has_only_constraints(self):
        ir = AgentExportIR(name="Focused Agent", constraints=["no network access"])
        assert _agent_output_is_usable(ir, "some markdown") is True

    def test_usable_when_ir_has_only_workflows(self):
        ir = AgentExportIR(name="Focused Agent", workflows=["run tests then deploy"])
        assert _agent_output_is_usable(ir, "some markdown") is True

    def test_rejects_empty_markdown(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, "") is False

    def test_rejects_whitespace_only_markdown(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, "   \n\t  ") is False

    def test_rejects_none_markdown(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, None) is False

    def test_rejects_failed_to_generate_marker(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, "Failed to generate response") is False

    def test_rejects_failed_to_generate_marker_case_insensitive(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, "FAILED TO GENERATE due to timeout") is False

    def test_rejects_api_key_is_missing_marker(self):
        ir = AgentExportIR(name="Focused Agent", role="Does things")
        assert _agent_output_is_usable(ir, "Error: API key is missing") is False

    def test_rejects_default_error_name(self):
        ir = AgentExportIR(name="Error", role="Does things")
        assert _agent_output_is_usable(ir, "some markdown") is False

    def test_rejects_default_placeholder_name_ai_agent(self):
        # AgentExportIR() defaults name to "AI Agent" -- the untouched default
        # must never be treated as usable, even with real-looking fields.
        ir = AgentExportIR(role="Does things", goals=["ship it"])
        assert ir.name == "AI Agent"
        assert _agent_output_is_usable(ir, "some markdown") is False

    def test_rejects_placeholder_name_case_and_whitespace_insensitive(self):
        ir = AgentExportIR(name="  ai AGENT  ", role="Does things")
        assert _agent_output_is_usable(ir, "some markdown") is False

    def test_rejects_when_all_content_fields_empty(self):
        ir = AgentExportIR(name="Real Name")
        assert not (ir.role or ir.goals or ir.constraints or ir.workflows)
        assert _agent_output_is_usable(ir, "some markdown") is False


# ---------------------------------------------------------------------------
# _skill_output_is_usable
# ---------------------------------------------------------------------------


class TestSkillOutputIsUsable:
    def test_usable_when_markdown_present_and_ir_has_purpose(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates consistently")
        assert _skill_output_is_usable(ir, "# format_dates\n\nDoes things") is True

    def test_usable_when_ir_has_only_implementation(self):
        ir = SkillExportIR(name="format_dates", implementation="return date.isoformat()")
        assert _skill_output_is_usable(ir, "some markdown") is True

    def test_usable_when_ir_has_only_params(self):
        from app.adapters.skill_ir import SkillParam

        ir = SkillExportIR(name="format_dates", params=[SkillParam(name="value", type="str")])
        assert _skill_output_is_usable(ir, "some markdown") is True

    def test_rejects_empty_markdown(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "") is False

    def test_rejects_whitespace_only_markdown(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "\n   ") is False

    def test_rejects_none_markdown(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates")
        assert _skill_output_is_usable(ir, None) is False

    def test_rejects_failed_to_generate_marker(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "failed to generate skill") is False

    def test_rejects_api_key_is_missing_marker(self):
        ir = SkillExportIR(name="format_dates", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "API Key is missing, cannot proceed") is False

    def test_rejects_default_error_name(self):
        ir = SkillExportIR(name="error", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "some markdown") is False

    def test_rejects_default_placeholder_name_skill_name(self):
        # SkillExportIR() defaults name to "skill_name" -- must never be
        # trusted even if purpose/params/implementation look real.
        ir = SkillExportIR(purpose="Formats dates", implementation="do it")
        assert ir.name == "skill_name"
        assert _skill_output_is_usable(ir, "some markdown") is False

    def test_rejects_placeholder_name_case_and_whitespace_insensitive(self):
        ir = SkillExportIR(name="  SKILL_NAME  ", purpose="Formats dates")
        assert _skill_output_is_usable(ir, "some markdown") is False

    def test_rejects_when_all_content_fields_empty(self):
        ir = SkillExportIR(name="real_name")
        assert not (ir.purpose or ir.params or ir.implementation)
        assert _skill_output_is_usable(ir, "some markdown") is False
