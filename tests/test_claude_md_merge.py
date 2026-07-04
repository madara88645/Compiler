from app.repo_inspect.claude_md_merge import MARKER, merge_claude_md


def test_preserve_prefix_and_append_new():
    existing = "# My Guide\n\n## Setup\nrun make\n"
    generated = "# Gen\n\n## Setup\nother setup\n\n## Deploy\nship it\n"
    merged = merge_claude_md(existing, generated)
    # existing content is preserved verbatim as the prefix (up to the marker)
    assert merged.startswith(existing.rstrip())
    assert merged.split("\n\n" + MARKER, 1)[0] == existing.rstrip()
    # only the section the user lacks is appended
    assert "## Deploy\nship it" in merged
    # the generated "Setup" body is NOT appended (heading already present)
    assert "other setup" not in merged


def test_no_new_sections_returns_existing_unchanged():
    existing = "# G\n\n## Setup\na\n\n## Deploy\nb\n"
    generated = "# Gen\n\n## setup\nx\n\n## DEPLOY\ny\n"  # same keys, different case
    assert merge_claude_md(existing, generated) == existing


def test_idempotent():
    existing = "# G\n\n## Setup\na\n"
    generated = "# Gen\n\n## Setup\na\n\n## Deploy\nb\n"
    once = merge_claude_md(existing, generated)
    assert merge_claude_md(once, generated) == once


def test_same_heading_different_body_is_dropped():
    # Accepted limitation: same heading key -> generated section not merged.
    existing = "## Security\nshort\n"
    generated = "## Security\nlong detailed policy\n"
    assert merge_claude_md(existing, generated) == existing


def test_duplicate_key_within_generated_appended_once():
    existing = "# Title only\n"
    generated = "## Setup\na\n\n## setup\nb\n"
    merged = merge_claude_md(existing, generated)
    assert merged.count("<!--") == 1
    assert merged.count("## Setup") + merged.count("## setup") == 1


def test_existing_without_sections_appends_all():
    existing = "# Just a title\n"
    generated = "## A\nx\n\n## B\ny\n"
    merged = merge_claude_md(existing, generated)
    assert "## A\nx" in merged
    assert "## B\ny" in merged


def test_generated_without_sections_returns_existing():
    existing = "# G\n\n## Setup\na\n"
    generated = "# Gen\n\nsome intro prose only\n"
    assert merge_claude_md(existing, generated) == existing


def test_heading_without_space_is_not_a_heading():
    existing = "# G\n"
    generated = "##NotAHeading\nbody\n\n## Real\nkeep\n"
    merged = merge_claude_md(existing, generated)
    # only "## Real" is a section; "##NotAHeading" is before the first real heading
    assert "## Real\nkeep" in merged
    assert "##NotAHeading" not in merged


def test_fence_in_generated_not_a_heading():
    existing = "# G\n"
    generated = "## Code\n```\n## inside fence\n```\nafter\n\n## Real\nkeep\n"
    merged = merge_claude_md(existing, generated)
    # "## inside fence" stays inside the Code section body, not a separate section
    assert "## inside fence" in merged
    assert merged.count("<!--") == 1  # single marker
    assert "## Code" in merged and "## Real" in merged


def test_fence_in_existing_does_not_shadow_generated_heading():
    existing = "# G\n\n```\n## Deploy\nfake\n```\n"
    generated = "## Deploy\nreal deploy steps\n"
    merged = merge_claude_md(existing, generated)
    # the fenced "## Deploy" in existing is NOT a real heading, so generated Deploy IS added
    assert "real deploy steps" in merged


def test_mixed_fence_delimiters():
    existing = "# G\n"
    generated = "## A\nx\n\n~~~\n```\n## Y\n~~~\n\n## B\nz\n"
    merged = merge_claude_md(existing, generated)
    # "## Y" is inside the ~~~ block (not closed by ```), so not its own section
    assert "## A" in merged and "## B" in merged
    assert "## Y" in merged  # present, but as body of section A


def test_crlf_existing_preserved():
    existing = "# Guide\r\n\r\n## Setup\r\nrun\r\n"
    generated = "## Deploy\nship\n"
    merged = merge_claude_md(existing, generated)
    assert merged.startswith("# Guide\r\n")
    assert "\r\n## Setup\r\nrun" in merged
