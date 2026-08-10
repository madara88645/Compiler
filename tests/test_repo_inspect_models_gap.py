"""tests/test_repo_inspect_models_gap.py — direct unit tests for
app.repo_inspect.models.RepoContext.command_map / .stack_summary, which had
no dedicated test coverage. Both are pure derived-property methods over
plain dataclass instances, no I/O involved.
"""

from app.repo_inspect.models import DetectedCommand, RepoContext, StackInfo


# --- command_map ---


def test_command_map_empty_commands_returns_empty_dict():
    ctx = RepoContext()
    assert ctx.command_map() == {}


def test_command_map_single_command_per_name():
    ctx = RepoContext(
        commands=[
            DetectedCommand(name="test", command="npm run test", source="web/package.json"),
            DetectedCommand(name="build", command="npm run build", source="web/package.json"),
        ]
    )

    assert ctx.command_map() == {
        "test": "npm run test",
        "build": "npm run build",
    }


def test_command_map_first_detected_wins_on_duplicate_name():
    ctx = RepoContext(
        commands=[
            DetectedCommand(name="test", command="npm run test", source="web/package.json"),
            DetectedCommand(name="test", command="pytest tests/ -q", source="Makefile"),
        ]
    )

    # setdefault semantics: the first "test" command encountered wins.
    assert ctx.command_map()["test"] == "npm run test"


# --- stack_summary ---


def test_stack_summary_empty_stacks_returns_empty_string():
    ctx = RepoContext()
    assert ctx.stack_summary() == ""


def test_stack_summary_languages_only_no_frameworks():
    ctx = RepoContext(stacks=[StackInfo(language="python"), StackInfo(language="go")])

    assert ctx.stack_summary() == "go, python"


def test_stack_summary_languages_and_frameworks_are_sorted_and_deduped():
    ctx = RepoContext(
        stacks=[
            StackInfo(language="python", frameworks=("fastapi", "pytest")),
            StackInfo(language="javascript", frameworks=("next", "fastapi")),
        ]
    )

    assert ctx.stack_summary() == "javascript, python / fastapi, next, pytest"


def test_stack_summary_single_stack_with_single_framework():
    ctx = RepoContext(stacks=[StackInfo(language="rust", frameworks=("actix",))])

    assert ctx.stack_summary() == "rust / actix"
