"""Unit tests for app.compile_export.render_compile_export.

This pure Markdown-rendering function has no dedicated test file even though
it backs both the API compile-export endpoint and the CLI compile-export
command (see tests/test_cli_compile_export.py, which only exercises it
indirectly through the CLI). These tests cover the function directly.
"""

from __future__ import annotations

from app.compile_export import render_compile_export


def _render(**overrides: str) -> str:
    fields = {
        "system_prompt": "You are a helpful assistant.",
        "user_prompt": "Summarize the attached document.",
        "plan": "1. Read document\n2. Summarize",
        "readiness_markdown": "## Readiness\n\nScore: 92",
    }
    fields.update(overrides)
    return render_compile_export(**fields)


def test_includes_title_and_all_section_headings():
    result = _render()
    assert result.startswith("# Prompt Compiler Export\n\n")
    assert "## System Prompt" in result
    assert "## User Prompt" in result
    assert "## Plan" in result


def test_embeds_each_field_verbatim_under_its_heading():
    result = _render()
    assert "You are a helpful assistant." in result
    assert "Summarize the attached document." in result
    assert "1. Read document\n2. Summarize" in result
    assert "## Readiness\n\nScore: 92" in result


def test_sections_appear_in_fixed_order():
    result = _render()
    title_idx = result.index("# Prompt Compiler Export")
    system_idx = result.index("## System Prompt")
    user_idx = result.index("## User Prompt")
    plan_idx = result.index("## Plan")
    readiness_idx = result.index("## Readiness")
    assert title_idx < system_idx < user_idx < plan_idx < readiness_idx


def test_strips_leading_and_trailing_whitespace_from_prompt_plan_fields():
    result = _render(
        system_prompt="  \n  System with padding  \n\n",
        user_prompt="\tUser with tab padding\t\n",
        plan="\n  Plan with padding  \n",
    )
    assert "## System Prompt\n\nSystem with padding\n\n" in result
    assert "## User Prompt\n\nUser with tab padding\n\n" in result
    assert "## Plan\n\nPlan with padding\n\n" in result
    # No stray leading whitespace should survive right after each heading.
    assert "System Prompt\n\n " not in result
    assert "User Prompt\n\n\t" not in result


def test_readiness_markdown_is_right_stripped_but_not_left_stripped():
    result = _render(readiness_markdown="  ## Readiness\n\nScore: 50  \n\n\n")
    # Leading spaces before "## Readiness" are preserved (only rstrip is applied).
    assert result.endswith("  ## Readiness\n\nScore: 50\n")


def test_document_ends_with_single_trailing_newline():
    result = _render()
    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_handles_empty_string_fields_without_error():
    result = render_compile_export(
        system_prompt="",
        user_prompt="",
        plan="",
        readiness_markdown="",
    )
    assert "## System Prompt\n\n\n\n" in result
    assert "## User Prompt\n\n\n\n" in result
    assert "## Plan\n\n\n\n" in result
    assert result.endswith("\n")


def test_multiline_plan_is_preserved_as_is_aside_from_outer_strip():
    plan = "Step 1: gather\nStep 2: analyze\nStep 3: report"
    result = _render(plan=plan)
    assert plan in result
