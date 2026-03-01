from rich.console import Console
from typer.testing import CliRunner

from cli.commands.core import app
import cli.commands.core
runner = CliRunner()

def test_fix_command_console_usage():
    """Test that the fix command runs without error and produces output,
    verifying that the global console object is working correctly."""

    # We patch the global console in the module with a new one that captures output
    # Since CliRunner captures stdout/stderr, using Console() (which defaults to sys.stdout)
    # inside the test context *should* write to the captured stream if rich respects sys.stdout changes.
    # However, to be absolutely sure, we replace the module-level console with one explicitly
    # created during the test run (which will see the patched stdout).

    original_console = cli.commands.core.console
    try:
        # Create a new console that will use the current stdout (patched by runner)
        # force_terminal=True ensures rich formatting codes are present if we want to check them,
        # but for simple text checks, default is fine.
        cli.commands.core.console = Console(force_terminal=True)

        # "do something" is vague enough to trigger fixes in the heuristics
        result = runner.invoke(app, ["fix", "do something"], input="n\n")

        assert result.exit_code == 0

        # Verify output was captured
        assert "Auto-Fix Report" in result.stdout
        assert "vague" in result.stdout.lower() or "improvement" in result.stdout.lower()

    finally:
        cli.commands.core.console = original_console

def test_compare_command_console_usage():
    """Test that the compare command runs without error and produces output,
    verifying that the global console object is working correctly."""

    original_console = cli.commands.core.console
    try:
        cli.commands.core.console = Console(force_terminal=True)

        # Compare two simple strings
        result = runner.invoke(app, ["compare", "write code", "write better code"])

        assert result.exit_code == 0

        assert "Prompt Comparison" in result.stdout
        assert "Validation Scores" in result.stdout

    finally:
        cli.commands.core.console = original_console
