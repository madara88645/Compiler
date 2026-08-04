"""Direct unit tests for the pure parsing helpers in app.repo_inspect.detect.

test_repo_inspect.py already covers these through derive_repo_context(); this
file targets parse_package_json_scripts, parse_makefile_targets, and
detect_stacks directly, including edge cases (malformed input, alias mapping,
recipe-line boundaries) that aren't reachable/asserted through the
higher-level integration tests.
"""

from app.repo_inspect.detect import (
    detect_stacks,
    parse_makefile_targets,
    parse_package_json_scripts,
)
from app.repo_inspect.models import DetectedCommand, StackInfo


# --- parse_package_json_scripts ---------------------------------------------


def test_parse_package_json_scripts_malformed_json_returns_empty():
    assert parse_package_json_scripts("{not valid json", "package.json") == []


def test_parse_package_json_scripts_non_dict_scripts_returns_empty():
    assert parse_package_json_scripts('{"scripts": ["test"]}', "package.json") == []


def test_parse_package_json_scripts_missing_scripts_key_returns_empty():
    assert parse_package_json_scripts('{"name": "x"}', "package.json") == []


def test_parse_package_json_scripts_maps_known_aliases():
    content = '{"scripts": {"test": "vitest run", "fmt": "prettier --write .", "start": "vite"}}'
    cmds = parse_package_json_scripts(content, "web/package.json")
    by_name = {c.name: c for c in cmds}
    assert by_name["test"] == DetectedCommand(
        name="test", command="npm run test", source="web/package.json"
    )
    # "fmt" aliases to the canonical "format" name.
    assert by_name["format"].command == "npm run fmt"
    # "start" aliases to the canonical "dev" name.
    assert by_name["dev"].command == "npm run start"


def test_parse_package_json_scripts_ignores_unknown_script_names():
    cmds = parse_package_json_scripts('{"scripts": {"deploy": "vercel"}}', "package.json")
    assert cmds == []


# --- parse_makefile_targets --------------------------------------------------


def test_parse_makefile_targets_picks_first_tab_indented_recipe_line():
    content = "test:\n\tpytest -q\n\techo done\nbuild:\n\techo build\n"
    cmds = parse_makefile_targets(content, "Makefile")
    by_name = {c.name: c.command for c in cmds}
    assert by_name["test"] == "pytest -q"
    assert by_name["build"] == "echo build"


def test_parse_makefile_targets_falls_back_to_make_target_when_no_recipe():
    content = "lint:\nbuild:\n\techo build\n"
    cmds = parse_makefile_targets(content, "Makefile")
    by_name = {c.name: c.command for c in cmds}
    assert by_name["lint"] == "make lint"


def test_parse_makefile_targets_stops_scanning_recipe_at_non_indented_line():
    # A blank/non-tab line right after the target means "no recipe" even
    # though a tab-indented line exists further down (belongs to another target).
    content = "lint:\n\ndeploy:\n\techo unrelated\n"
    cmds = parse_makefile_targets(content, "Makefile")
    by_name = {c.name: c.command for c in cmds}
    assert by_name["lint"] == "make lint"


def test_parse_makefile_targets_ignores_unaliased_targets():
    content = "deploy:\n\techo deploy\n"
    assert parse_makefile_targets(content, "Makefile") == []


def test_parse_makefile_targets_ignores_variable_assignments():
    # "FOO:=bar" looks target-like but the regex explicitly excludes ":=" lines.
    content = "FOO:=bar\ntest:\n\techo t\n"
    cmds = parse_makefile_targets(content, "Makefile")
    assert [c.name for c in cmds] == ["test"]


# --- detect_stacks ------------------------------------------------------------


def test_detect_stacks_empty_files_returns_empty_list():
    assert detect_stacks({}) == []


def test_detect_stacks_ignores_unrecognized_manifest_names():
    assert detect_stacks({"README.md": "next react fastapi"}) == []


def test_detect_stacks_multiple_languages_sorted_by_language_name():
    files = {
        "go.mod": "module example.com/x\n",
        "package.json": '{"dependencies": {"react": "18.0.0"}}',
    }
    stacks = detect_stacks(files)
    assert [s.language for s in stacks] == ["go", "javascript"]
    assert stacks[1] == StackInfo(language="javascript", frameworks=("react",))


def test_detect_stacks_frameworks_are_sorted_and_deduplicated_per_language():
    files = {
        "package.json": '{"dependencies": {"react": "18", "vue": "3"}}',
        "pom.xml": "<project></project>",
    }
    stacks = detect_stacks(files)
    js_stack = next(s for s in stacks if s.language == "javascript")
    assert js_stack.frameworks == ("react", "vue")
