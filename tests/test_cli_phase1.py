from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

DEPRECATED = ["favorites", "snippets", "collections", "palette"]


def test_help_lists_no_deprecated_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in DEPRECATED:
        assert name not in result.stdout, f"deprecated command still listed: {name}"


from app import get_version


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == get_version()
