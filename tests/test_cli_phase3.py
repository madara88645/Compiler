"""Phase 3 (CLI code health) safety net.

These tests pin the externally observable CLI surface so the core.py split
into focused modules can be verified as behavior-preserving. They must pass
BEFORE the split (on the monolithic core.py) and remain green after.
"""

from typer.testing import CliRunner

from cli.commands.core import app as core_app
from cli.main import app as main_app

_runner = CliRunner()

# The complete set of top-level commands registered on the core Typer app.
# The split must preserve this set byte-for-byte.
EXPECTED_TOP_LEVEL_COMMANDS = {
    "batch",
    "compare",
    "compile",
    "diff",
    "fix",
    "json-path",
    "pack",
    "validate",
    "version",
}


def test_top_level_command_surface_invariant():
    # registered_commands holds only the @app.command() leaf commands; sub-apps
    # mounted via add_typer in cli.main go to a separate registered_groups list,
    # so this assertion is independent of import order. The Phase 3 split must
    # preserve exactly this set.
    names = {
        ci.name or ci.callback.__name__.replace("_", "-") for ci in core_app.registered_commands
    }
    assert names == EXPECTED_TOP_LEVEL_COMMANDS


def test_fix_command_runs():
    result = _runner.invoke(main_app, ["fix", "write something useful"])
    assert result.exit_code == 0, result.output


def test_compare_command_runs():
    result = _runner.invoke(
        main_app, ["compare", "summarize this text", "summarize the text in three bullets"]
    )
    assert result.exit_code == 0, result.output


def test_pack_command_runs():
    result = _runner.invoke(main_app, ["pack", "build a rest api", "--format", "md"])
    assert result.exit_code == 0, result.output
