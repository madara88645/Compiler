"""Unit tests for app.utils prompt-pack renderers.

`_render_prompt_pack_md` and `_render_prompt_pack_txt` assemble the
downloadable "prompt pack" from its four sections. They were previously
untested; these tests pin down section ordering, the custom title, the
omission of empty sections, and the surrounding-whitespace strip.
"""

from app.utils import _render_prompt_pack_md, _render_prompt_pack_txt


def test_md_includes_all_sections_in_order() -> None:
    out = _render_prompt_pack_md("sys", "usr", "plan", "exp")
    assert out.startswith("# Prompt Pack")
    # Sections appear in declaration order.
    assert (
        out.index("## System Prompt")
        < out.index("## User Prompt")
        < out.index("## Plan")
        < out.index("## Expanded Prompt")
    )
    for body in ("sys", "usr", "plan", "exp"):
        assert body in out


def test_md_uses_custom_title() -> None:
    out = _render_prompt_pack_md("sys", "", "", "", title="My Pack")
    assert out.startswith("# My Pack")


def test_md_omits_empty_sections() -> None:
    out = _render_prompt_pack_md("sys", "", "plan", "")
    assert "## System Prompt" in out
    assert "## Plan" in out
    assert "## User Prompt" not in out
    assert "## Expanded Prompt" not in out


def test_md_strips_surrounding_whitespace() -> None:
    # Only the title is present, so the result is exactly the heading (stripped).
    assert _render_prompt_pack_md("", "", "", "") == "# Prompt Pack"


def test_txt_includes_all_sections_in_order() -> None:
    out = _render_prompt_pack_txt("sys", "usr", "plan", "exp")
    assert (
        out.index("--- System Prompt ---")
        < out.index("--- User Prompt ---")
        < out.index("--- Plan ---")
        < out.index("--- Expanded Prompt ---")
    )
    for body in ("sys", "usr", "plan", "exp"):
        assert body in out


def test_txt_omits_empty_sections() -> None:
    out = _render_prompt_pack_txt("", "usr", "", "exp")
    assert "--- User Prompt ---" in out
    assert "--- Expanded Prompt ---" in out
    assert "--- System Prompt ---" not in out
    assert "--- Plan ---" not in out


def test_txt_empty_input_renders_empty_string() -> None:
    assert _render_prompt_pack_txt("", "", "", "") == ""
