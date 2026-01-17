from pathlib import Path
from app.tui import TestFileItem, SearchApp
from cli.commands.testing import test_run as command_test_run


def test_test_file_item_rendering():
    path = Path("tests/suite.yml")
    item = TestFileItem(path)
    rendered = item.render()

    assert "🧪" in rendered.plain
    assert "suite.yml" in rendered.plain
    assert "tests" in rendered.plain


def test_app_has_f10_binding():
    bindings = SearchApp.BINDINGS
    binding_keys = [b.key for b in bindings]
    assert "f10" in binding_keys

    f10 = next(b for b in bindings if b.key == "f10")
    assert f10.action == "show_test_mode"


def test_app_has_test_mode_flag():
    app = SearchApp()
    assert hasattr(app, "test_mode")
    assert app.test_mode is False
    assert hasattr(app, "test_runner")


def test_app_has_action_show_test_mode():
    app = SearchApp()
    assert hasattr(app, "action_show_test_mode")
    assert callable(app.action_show_test_mode)


def test_cli_command_exists():
    assert callable(command_test_run)
