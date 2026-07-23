"""Direct unit tests for app/repo_inspect/detect.py parsers and RepoContext helpers.

These are reached indirectly through derive_repo_context (see test_repo_inspect.py)
but the individual parser functions and RepoContext helpers have no direct
boundary-condition tests of their own today.
"""

from app.repo_inspect.detect import (
    detect_stacks,
    parse_makefile_targets,
    parse_package_json_scripts,
)
from app.repo_inspect.models import DetectedCommand, RepoContext, StackInfo


# ---------------------------------------------------------------------------
# parse_package_json_scripts
# ---------------------------------------------------------------------------


def test_parse_package_json_scripts_extracts_known_aliases():
    content = '{"scripts": {"test": "vitest run", "build": "next build", "lint": "eslint ."}}'
    cmds = parse_package_json_scripts(content, "package.json")
    by_name = {c.name: c.command for c in cmds}
    assert by_name == {
        "test": "npm run test",
        "build": "npm run build",
        "lint": "npm run lint",
    }
    assert all(c.source == "package.json" for c in cmds)


def test_parse_package_json_scripts_maps_start_to_dev_alias():
    content = '{"scripts": {"start": "node server.js"}}'
    cmds = parse_package_json_scripts(content, "package.json")
    assert cmds == [DetectedCommand(name="dev", command="npm run start", source="package.json")]


def test_parse_package_json_scripts_ignores_unknown_script_names():
    content = '{"scripts": {"deploy": "vercel deploy"}}'
    assert parse_package_json_scripts(content, "package.json") == []


def test_parse_package_json_scripts_returns_empty_for_invalid_json():
    assert parse_package_json_scripts("{not valid json", "package.json") == []


def test_parse_package_json_scripts_returns_empty_when_scripts_not_a_dict():
    content = '{"scripts": ["test"]}'
    assert parse_package_json_scripts(content, "package.json") == []


def test_parse_package_json_scripts_returns_empty_when_scripts_missing():
    assert parse_package_json_scripts("{}", "package.json") == []


# ---------------------------------------------------------------------------
# parse_makefile_targets
# ---------------------------------------------------------------------------


def test_parse_makefile_targets_extracts_recipe_line():
    content = "test:\n\tpython -m pytest tests/ -q\nbuild:\n\techo build\n"
    cmds = parse_makefile_targets(content, "Makefile")
    by_name = {c.name: c.command for c in cmds}
    assert by_name == {"test": "python -m pytest tests/ -q", "build": "echo build"}


def test_parse_makefile_targets_falls_back_to_make_target_when_no_recipe():
    content = "lint:\n\n"
    cmds = parse_makefile_targets(content, "Makefile")
    assert cmds == [DetectedCommand(name="lint", command="make lint", source="Makefile")]


def test_parse_makefile_targets_ignores_unaliased_targets():
    content = "deploy:\n\techo deploy\n"
    assert parse_makefile_targets(content, "Makefile") == []


def test_parse_makefile_targets_ignores_variable_assignments():
    # `FOO:=bar` looks like a target but the `(?!=)` guard should exclude it.
    content = "test:=disabled\n"
    assert parse_makefile_targets(content, "Makefile") == []


def test_parse_makefile_targets_stops_recipe_scan_at_next_non_indented_line():
    content = "test:\nbuild:\n\techo build\n"
    cmds = parse_makefile_targets(content, "Makefile")
    by_name = {c.name: c.command for c in cmds}
    # "test" has no tab-indented recipe line before the next target, so it falls back.
    assert by_name["test"] == "make test"
    assert by_name["build"] == "echo build"


# ---------------------------------------------------------------------------
# detect_stacks
# ---------------------------------------------------------------------------


def test_detect_stacks_maps_manifest_to_language():
    files = {"go.mod": "module example.com/foo\n"}
    stacks = detect_stacks(files)
    assert stacks == [StackInfo(language="go", frameworks=())]


def test_detect_stacks_detects_framework_by_word_boundary():
    files = {"package.json": '{"dependencies": {"express": "4.18.0"}}'}
    stacks = detect_stacks(files)
    assert stacks == [StackInfo(language="javascript", frameworks=("express",))]


def test_detect_stacks_ignores_substring_framework_matches():
    files = {"package.json": '{"name": "preact-playground"}'}
    stacks = detect_stacks(files)
    assert stacks == [StackInfo(language="javascript", frameworks=())]


def test_detect_stacks_merges_multiple_manifests_for_same_language():
    files = {
        "requirements.txt": "flask==3.0.0\n",
        "pyproject.toml": '[project]\ndependencies = ["fastapi"]\n',
    }
    stacks = detect_stacks(files)
    assert stacks == [StackInfo(language="python", frameworks=("fastapi", "flask"))]


def test_detect_stacks_ignores_unknown_manifest_files():
    assert detect_stacks({"README.md": "# hello"}) == []


def test_detect_stacks_returns_sorted_language_list():
    files = {"go.mod": "module x\n", "package.json": "{}"}
    stacks = detect_stacks(files)
    assert [s.language for s in stacks] == ["go", "javascript"]


# ---------------------------------------------------------------------------
# RepoContext.command_map / stack_summary
# ---------------------------------------------------------------------------


def test_command_map_keeps_first_command_per_name():
    ctx = RepoContext(
        commands=[
            DetectedCommand(name="test", command="npm run test", source="package.json"),
            DetectedCommand(name="test", command="make test", source="Makefile"),
            DetectedCommand(name="build", command="npm run build", source="package.json"),
        ]
    )
    assert ctx.command_map() == {"test": "npm run test", "build": "npm run build"}


def test_command_map_empty_when_no_commands():
    assert RepoContext().command_map() == {}


def test_stack_summary_combines_languages_and_frameworks():
    ctx = RepoContext(
        stacks=[
            StackInfo(language="python", frameworks=("fastapi",)),
            StackInfo(language="javascript", frameworks=("next", "react")),
        ]
    )
    assert ctx.stack_summary() == "javascript, python / fastapi, next, react"


def test_stack_summary_omits_frameworks_section_when_none_detected():
    ctx = RepoContext(stacks=[StackInfo(language="go", frameworks=())])
    assert ctx.stack_summary() == "go"


def test_stack_summary_empty_for_no_stacks():
    assert RepoContext().stack_summary() == ""
