from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

DEPRECATED = ["favorites", "snippets", "collections", "palette"]


def test_help_lists_no_deprecated_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in DEPRECATED:
        assert name not in result.stdout, f"deprecated command still listed: {name}"
