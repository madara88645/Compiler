from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.instruction_review import (
    InstructionReviewRequest,
    analyze_instruction_review,
)


def _review(content: str, *, path: str = "CLAUDE.md", known_repo_files: list[str] | None = None):
    request = InstructionReviewRequest(
        files=[{"path": path, "content": content}],
        known_repo_files=known_repo_files,
    )
    return analyze_instruction_review(request)


def test_exact_adjacent_duplicate_is_reported_and_suggested_once_removed():
    original = "# Rules\n\n- Keep changes small.\n- Keep changes small.\n"

    response = _review(original)

    duplicate = [finding for finding in response.findings if finding.kind == "duplicate_rule"]
    assert len(duplicate) == 1
    assert duplicate[0].severity == "info"
    assert duplicate[0].line == 4
    assert [location.model_dump() for location in duplicate[0].related] == [
        {"path": "CLAUDE.md", "line": 3}
    ]
    assert response.files[0].original == original
    assert response.files[0].suggested == "# Rules\n\n- Keep changes small.\n"
    assert response.files[0].diff.startswith("--- CLAUDE.md\n+++ CLAUDE.md (suggested)\n@@")
    assert response.summary.duplicate_lines_removed == 1


def test_duplicate_key_keeps_internal_whitespace_exact_and_diff_handles_missing_final_newline():
    original = "- Run `pytest   -q`.\n- Run `pytest -q`.\n- Run `pytest   -q`."

    response = _review(original)

    assert response.summary.duplicate_lines_removed == 0
    assert response.files[0].suggested == original

    removable = _review("- Keep this line.\n- Keep this line.")
    assert removable.summary.duplicate_lines_removed == 1
    assert "\\ No newline at end of file" in removable.files[0].diff
    assert removable.files[0].diff.splitlines()[:3] == [
        "--- CLAUDE.md",
        "+++ CLAUDE.md (suggested)",
        "@@ -1,2 +1 @@",
    ]


def test_same_prose_in_different_scopes_or_files_is_kept_for_review():
    response = analyze_instruction_review(
        InstructionReviewRequest(
            files=[
                {
                    "path": "CLAUDE.md",
                    "content": (
                        "# Rules\n- Keep changes small.\n\n"
                        "For backend:\n- Keep changes small.\n\n"
                        "## Frontend\n- Keep changes small.\n"
                    ),
                },
                {"path": "AGENTS.md", "content": "# Rules\n- Keep changes small.\n"},
            ]
        )
    )

    duplicate = [finding for finding in response.findings if finding.kind == "duplicate_rule"]
    assert len(duplicate) == 3
    assert response.summary.duplicate_lines_removed == 0
    assert all(file.original == file.suggested for file in response.files)
    assert all(finding.severity == "warning" for finding in duplicate)


def test_checkbox_state_and_parent_rules_with_children_are_never_auto_removed():
    original = (
        "- [ ] Run tests.\n"
        "- [x] Run tests.\n"
        "- [x] Run tests.\n"
        "- Always do X:\n"
        "- Always do X:\n"
        "  - Keep its child attached.\n"
    )

    response = _review(original)

    assert response.files[0].suggested == original
    assert response.summary.duplicate_lines_removed == 0
    duplicates = [finding for finding in response.findings if finding.kind == "duplicate_rule"]
    assert {finding.line for finding in duplicates} == {3, 5}
    assert all(finding.severity == "warning" for finding in duplicates)


def test_collapsible_blocks_are_separate_scopes():
    response = _review(
        "<details>\n<summary>First</summary>\n- Keep this rule.\n- Keep this rule.\n</details>\n"
        "<details>\n<summary>Second</summary>\n- Keep this rule.\n- Keep this rule.\n</details>\n"
    )

    assert response.summary.duplicate_lines_removed == 2
    assert response.files[0].suggested.count("- Keep this rule.") == 2


def test_fences_must_match_marker_type_and_length_and_are_never_changed():
    original = (
        "# Rules\n"
        "- Keep changes small.\n"
        "- Keep changes small.\n"
        "```md\n"
        "- Keep changes small.\n"
        "~~\n"
        "- Keep changes small.\n"
        "```\n"
        "- Keep changes small.\n"
    )

    response = _review(original)

    assert response.summary.duplicate_lines_removed == 1
    assert "- Keep changes small.\n~~\n- Keep changes small.\n```\n" in response.files[0].suggested
    assert response.files[0].suggested.count("- Keep changes small.") == 4


def test_conditions_numbered_nested_and_indented_rules_are_report_only():
    original = (
        "- Keep this condition if CI is enabled.\n"
        "- Keep this condition if CI is enabled.\n"
        "1. Keep the order.\n"
        "2. Keep the order.\n"
        "  - Keep the nested rule.\n"
        "  - Keep the nested rule.\n"
        "    Never remove this indented rule.\n"
        "    Never remove this indented rule.\n"
    )

    response = _review(original)

    assert response.summary.duplicate_lines_removed == 0
    assert response.files[0].suggested == original
    duplicates = [finding for finding in response.findings if finding.kind == "duplicate_rule"]
    assert len(duplicates) == 4
    assert all(finding.severity == "warning" for finding in duplicates)


def test_literal_command_polarity_is_a_potential_conflict_only():
    response = _review("- Never run `pytest -q`.\n- Always run `pytest -q`.\n")

    conflicts = [finding for finding in response.findings if finding.kind == "potential_conflict"]
    assert len(conflicts) == 1
    assert conflicts[0].severity == "warning"
    assert "literal command" in conflicts[0].message
    assert "review manually" in conflicts[0].message
    assert [location.model_dump() for location in conflicts[0].related] == [
        {"path": "CLAUDE.md", "line": 2}
    ]
    assert response.files[0].suggested == response.files[0].original


def test_relative_links_are_unverified_without_known_file_list():
    response = _review(
        "See [build](docs/build.md), [external](https://example.com), and [section](#rules).\n"
    )

    links = [finding for finding in response.findings if finding.kind == "stale_link"]
    assert len(links) == 1
    assert links[0].severity == "info"
    assert "not verified" in links[0].message
    assert "not present" not in links[0].message


def test_known_file_list_enables_conservative_stale_link_check():
    response = _review(
        "See [build](docs/build.md) and [missing](docs/missing.md).\n",
        known_repo_files=["CLAUDE.md", "docs/build.md"],
    )

    links = [finding for finding in response.findings if finding.kind == "stale_link"]
    assert len(links) == 1
    assert links[0].severity == "warning"
    assert "docs/missing.md" in links[0].message
    assert response.summary.stale_links == 1


def test_html_comments_do_not_create_stale_link_findings():
    response = _review(
        "<!--\n[hidden](docs/missing.md)\n-->\nSee [visible](docs/missing.md).\n",
        known_repo_files=["CLAUDE.md"],
    )

    links = [finding for finding in response.findings if finding.kind == "stale_link"]
    assert len(links) == 1
    assert links[0].line == 4


def test_import_note_explains_that_file_splitting_does_not_automatically_cut_context():
    response = _review("@.claude/rules/testing.md\n")

    notes = [finding for finding in response.findings if finding.kind == "context_split"]
    assert len(notes) == 1
    assert notes[0].severity == "info"
    assert "does not automatically cut context" in notes[0].message


@pytest.mark.parametrize(
    "path", ["../AGENTS.md", "/tmp/AGENTS.md", "C:\\repo\\AGENTS.md", "a/./b.md"]
)
def test_file_names_are_validated_as_relative_names_without_filesystem_access(path: str):
    with pytest.raises(ValidationError):
        InstructionReviewRequest(files=[{"path": path, "content": "rules"}])


def test_request_rejects_duplicate_names_and_configured_aggregate_limit(monkeypatch):
    with pytest.raises(ValidationError, match="duplicate"):
        InstructionReviewRequest(
            files=[
                {"path": "CLAUDE.md", "content": "a"},
                {"path": "CLAUDE.md", "content": "b"},
            ]
        )

    monkeypatch.setenv("PROMPTC_INSTRUCTION_REVIEW_MAX_TOTAL_CHARS", "10")
    with pytest.raises(ValidationError, match="aggregate"):
        InstructionReviewRequest(files=[{"path": "CLAUDE.md", "content": "01234567890"}])


def test_conflict_findings_and_related_locations_are_bounded():
    content = "".join(["- Never run `pytest -q`.\n"] * 300 + ["- Always run `pytest -q`.\n"] * 300)

    response = _review(content)

    conflicts = [finding for finding in response.findings if finding.kind == "potential_conflict"]
    assert len(conflicts) == 256
    assert all(len(finding.related) <= 8 for finding in conflicts)
    assert response.summary.potential_conflicts == 256
