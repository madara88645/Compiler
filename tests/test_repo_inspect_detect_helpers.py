"""Direct unit coverage for app.repo_inspect.detect's pure parsing helpers.

parse_package_json_scripts, parse_makefile_targets and detect_stacks feed
repo-aware command/stack detection used by agent-pack generation and
PR-safety checks. They previously had no dedicated test file — only
indirect, happy-path coverage via derive_repo_context in
test_repo_inspect.py. A bad regex or an unhandled edge case here silently
produces a wrong (or missing) build/test/lint command or stack for a scanned
repo, without raising an error.
"""

from app.repo_inspect.detect import (
    detect_stacks,
    parse_makefile_targets,
    parse_package_json_scripts,
)


class TestParsePackageJsonScripts:
    def test_malformed_json_returns_empty(self):
        assert parse_package_json_scripts("{not valid json", "package.json") == []

    def test_missing_scripts_key_returns_empty(self):
        assert parse_package_json_scripts('{"name": "x"}', "package.json") == []

    def test_scripts_not_a_dict_returns_empty(self):
        assert parse_package_json_scripts('{"scripts": ["test"]}', "package.json") == []

    def test_start_script_aliases_to_dev(self):
        cmds = parse_package_json_scripts('{"scripts": {"start": "node server.js"}}', "package.json")
        assert [(c.name, c.command) for c in cmds] == [("dev", "npm run start")]

    def test_fmt_script_aliases_to_format(self):
        cmds = parse_package_json_scripts('{"scripts": {"fmt": "prettier --write ."}}', "package.json")
        assert [(c.name, c.command) for c in cmds] == [("format", "npm run fmt")]

    def test_unrelated_script_name_is_ignored(self):
        cmds = parse_package_json_scripts('{"scripts": {"prepare": "husky install"}}', "package.json")
        assert cmds == []

    def test_source_is_preserved_on_each_command(self):
        cmds = parse_package_json_scripts('{"scripts": {"test": "vitest run"}}', "web/package.json")
        assert cmds[0].source == "web/package.json"


class TestParseMakefileTargets:
    def test_unknown_target_is_ignored(self):
        assert parse_makefile_targets("deploy:\n\tssh prod 'restart'\n", "Makefile") == []

    def test_target_without_recipe_falls_back_to_make_invocation(self):
        cmds = parse_makefile_targets("build:\n\n", "Makefile")
        assert [(c.name, c.command) for c in cmds] == [("build", "make build")]

    def test_only_first_tab_indented_recipe_line_is_used(self):
        content = "test:\n\tpython -m pytest tests/ -q\n\techo done\n"
        cmds = parse_makefile_targets(content, "Makefile")
        assert cmds[0].command == "python -m pytest tests/ -q"

    def test_blank_line_before_recipe_stops_lookup(self):
        # A blank/non-indented line right after the target header means there
        # is no recipe attached to it; must fall back rather than grabbing a
        # later, unrelated tab-indented line.
        content = "test:\n\nbuild:\n\techo build\n"
        cmds = parse_makefile_targets(content, "Makefile")
        by_name = {c.name: c.command for c in cmds}
        assert by_name["test"] == "make test"
        assert by_name["build"] == "echo build"

    def test_variable_assignment_with_colon_equals_is_not_a_target(self):
        assert parse_makefile_targets("VAR:=value\n", "Makefile") == []

    def test_target_name_with_dot_and_dash_is_matched(self):
        content = "test.unit-fast:\n\techo unit\n"
        # "test.unit-fast" has no alias entry, so it's ignored -- but this
        # exercises the regex accepting dots/dashes without raising.
        assert parse_makefile_targets(content, "Makefile") == []

    def test_source_is_preserved_on_each_command(self):
        cmds = parse_makefile_targets("lint:\n\truff check .\n", "backend/Makefile")
        assert cmds[0].source == "backend/Makefile"


class TestDetectStacks:
    def test_no_known_manifest_returns_empty(self):
        assert detect_stacks({"README.md": "# hello"}) == []

    def test_unknown_manifest_basename_is_ignored(self):
        assert detect_stacks({"some/weird.lock": "fastapi"}) == []

    def test_nested_path_uses_basename_for_manifest_lookup(self):
        stacks = detect_stacks({"services/api/requirements.txt": "fastapi==0.110\n"})
        assert [s.language for s in stacks] == ["python"]

    def test_framework_matching_is_case_insensitive(self):
        stacks = detect_stacks({"package.json": '{"dependencies": {"React": "18.0.0"}}'})
        assert stacks[0].frameworks == ("react",)

    def test_multiple_languages_sorted_by_name(self):
        stacks = detect_stacks(
            {
                "package.json": "{}",
                "go.mod": "module example.com/x\n",
                "pyproject.toml": "[project]\nname='x'\n",
            }
        )
        assert [s.language for s in stacks] == ["go", "javascript", "python"]

    def test_multiple_frameworks_for_same_language_are_sorted(self):
        stacks = detect_stacks(
            {"package.json": '{"dependencies": {"vue": "3.0.0", "express": "4.0.0"}}'}
        )
        assert stacks[0].frameworks == ("express", "vue")
