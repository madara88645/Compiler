from app.repo_inspect.detect import (
    detect_stacks,
    parse_makefile_targets,
    parse_package_json_scripts,
)


# --------------------------------------------------------------------------
# parse_package_json_scripts
# --------------------------------------------------------------------------


def test_parse_package_json_scripts_maps_known_aliases():
    content = '{"scripts": {"test": "vitest run", "build": "next build", "start": "next start"}}'
    cmds = parse_package_json_scripts(content, source="web/package.json")

    by_name = {c.name: c.command for c in cmds}
    assert by_name["test"] == "npm run test"
    assert by_name["build"] == "npm run build"
    # "start" aliases to canonical "dev"
    assert by_name["dev"] == "npm run start"
    assert all(c.source == "web/package.json" for c in cmds)


def test_parse_package_json_scripts_ignores_unknown_script_names():
    content = '{"scripts": {"deploy": "vercel --prod"}}'
    assert parse_package_json_scripts(content, source="package.json") == []


def test_parse_package_json_scripts_invalid_json_returns_empty_list():
    assert parse_package_json_scripts("not json {{{", source="package.json") == []


def test_parse_package_json_scripts_missing_scripts_key_returns_empty_list():
    assert parse_package_json_scripts("{}", source="package.json") == []


def test_parse_package_json_scripts_non_dict_scripts_value_returns_empty_list():
    content = '{"scripts": ["test"]}'
    assert parse_package_json_scripts(content, source="package.json") == []


# --------------------------------------------------------------------------
# parse_makefile_targets
# --------------------------------------------------------------------------


def test_parse_makefile_targets_uses_tab_indented_recipe_line():
    content = "test:\n\tpython -m pytest tests/ -q\n"
    cmds = parse_makefile_targets(content, source="Makefile")

    assert len(cmds) == 1
    assert cmds[0].name == "test"
    assert cmds[0].command == "python -m pytest tests/ -q"
    assert cmds[0].source == "Makefile"


def test_parse_makefile_targets_falls_back_to_make_target_without_recipe():
    content = "build:\nlint:\n\tflake8 .\n"
    cmds = parse_makefile_targets(content, source="Makefile")

    by_name = {c.name: c.command for c in cmds}
    assert by_name["build"] == "make build"
    assert by_name["lint"] == "flake8 ."


def test_parse_makefile_targets_ignores_unaliased_target_names():
    content = "deploy:\n\techo shipping\n"
    assert parse_makefile_targets(content, source="Makefile") == []


def test_parse_makefile_targets_ignores_variable_assignments():
    # "CC:=gcc" looks target-like but the `(?!=)` guard should exclude it.
    content = "CC:=gcc\ntest:\n\tgo test ./...\n"
    cmds = parse_makefile_targets(content, source="Makefile")
    assert [c.name for c in cmds] == ["test"]


def test_parse_makefile_targets_stops_recipe_search_at_next_non_indented_line():
    # No tab-indented recipe immediately follows "build:", so it should fall
    # back to "make build" rather than picking up "lint"'s recipe.
    content = "build:\nlint:\n\tflake8 .\n"
    cmds = parse_makefile_targets(content, source="Makefile")
    by_name = {c.name: c.command for c in cmds}
    assert by_name["build"] == "make build"


def test_parse_makefile_targets_empty_content_returns_empty_list():
    assert parse_makefile_targets("", source="Makefile") == []


# --------------------------------------------------------------------------
# detect_stacks
# --------------------------------------------------------------------------


def test_detect_stacks_groups_frameworks_by_language():
    files = {
        "package.json": '{"dependencies": {"react": "18.0.0", "next": "14.0.0"}}',
        "requirements.txt": "django==5.0\n",
    }
    stacks = detect_stacks(files)

    by_language = {s.language: set(s.frameworks) for s in stacks}
    assert by_language["javascript"] == {"react", "next"}
    assert by_language["python"] == {"django"}


def test_detect_stacks_ignores_unrecognized_manifest_files():
    files = {"README.md": "next react django flask"}
    assert detect_stacks(files) == []


def test_detect_stacks_no_files_returns_empty_list():
    assert detect_stacks({}) == []


def test_detect_stacks_merges_multiple_manifests_of_same_language():
    files = {
        "requirements.txt": "flask==3.0\n",
        "pyproject.toml": '[project]\ndependencies = ["fastapi"]\n',
    }
    stacks = detect_stacks(files)
    assert len(stacks) == 1
    assert stacks[0].language == "python"
    assert set(stacks[0].frameworks) == {"flask", "fastapi"}


def test_detect_stacks_returns_sorted_by_language():
    files = {
        "go.mod": "module example.com/x\n",
        "package.json": "{}",
    }
    stacks = detect_stacks(files)
    assert [s.language for s in stacks] == ["go", "javascript"]
