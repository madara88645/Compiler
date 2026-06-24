from typer.testing import CliRunner

from cli.main import app
from app import get_version

runner = CliRunner()

DEPRECATED = ["favorites", "snippets", "collections", "palette"]


def test_help_lists_no_deprecated_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in DEPRECATED:
        assert name not in result.stdout, f"deprecated command still listed: {name}"


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == get_version()


def test_short_version_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert result.stdout.strip() == get_version()


def test_bare_invocation_shows_help():
    result = runner.invoke(app, [])
    # no_args_is_help=True makes a bare invocation print help and exit 2
    assert result.exit_code == 2
    assert "Usage" in result.stdout
