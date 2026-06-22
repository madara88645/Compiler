"""Tests for pure rendering helpers in app.utils."""
from __future__ import annotations

import pytest

from app.utils import _render_prompt_pack_md, _render_prompt_pack_txt


class TestRenderPromptPackMd:
    def test_all_sections_included(self) -> None:
        result = _render_prompt_pack_md("sys", "usr", "plan", "exp", "MyTitle")
        assert "# MyTitle" in result
        assert "## System Prompt\n\nsys" in result
        assert "## User Prompt\n\nusr" in result
        assert "## Plan\n\nplan" in result
        assert "## Expanded Prompt\n\nexp" in result

    def test_default_title_is_prompt_pack(self) -> None:
        result = _render_prompt_pack_md("s", "u", "p", "e")
        assert result.startswith("# Prompt Pack")

    def test_empty_section_omitted(self) -> None:
        result = _render_prompt_pack_md("", "", "plan_only", "")
        assert "System Prompt" not in result
        assert "User Prompt" not in result
        assert "## Plan\n\nplan_only" in result
        assert "Expanded Prompt" not in result

    def test_all_empty_yields_title_only(self) -> None:
        result = _render_prompt_pack_md("", "", "", "", "T")
        assert result == "# T"

    def test_output_is_stripped(self) -> None:
        result = _render_prompt_pack_md("x", "", "", "")
        assert not result.startswith("\n")
        assert not result.endswith("\n")

    def test_content_appears_exactly_once(self) -> None:
        result = _render_prompt_pack_md("unique_sys", "unique_usr", "", "")
        assert result.count("unique_sys") == 1
        assert result.count("unique_usr") == 1

    def test_title_is_first_line(self) -> None:
        result = _render_prompt_pack_md("sys", "usr", "plan", "exp", "Header")
        assert result.index("# Header") == 0


class TestRenderPromptPackTxt:
    def test_all_sections_included(self) -> None:
        result = _render_prompt_pack_txt("sys", "usr", "plan", "exp")
        assert "--- System Prompt ---\nsys" in result
        assert "--- User Prompt ---\nusr" in result
        assert "--- Plan ---\nplan" in result
        assert "--- Expanded Prompt ---\nexp" in result

    def test_empty_section_omitted(self) -> None:
        result = _render_prompt_pack_txt("", "", "only_plan", "")
        assert "System Prompt" not in result
        assert "User Prompt" not in result
        assert "--- Plan ---\nonly_plan" in result
        assert "Expanded Prompt" not in result

    def test_all_empty_yields_empty_string(self) -> None:
        assert _render_prompt_pack_txt("", "", "", "") == ""

    def test_output_is_stripped(self) -> None:
        result = _render_prompt_pack_txt("only_sys", "", "", "")
        assert not result.startswith("\n")
        assert not result.endswith("\n")

    def test_sections_separated_by_blank_line(self) -> None:
        result = _render_prompt_pack_txt("s", "u", "", "")
        assert "\n\n--- User Prompt ---" in result

    def test_content_appears_exactly_once(self) -> None:
        result = _render_prompt_pack_txt("unique_sys", "unique_usr", "", "")
        assert result.count("unique_sys") == 1
        assert result.count("unique_usr") == 1
