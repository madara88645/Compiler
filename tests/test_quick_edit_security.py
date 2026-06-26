# ruff: noqa: E402
import os
import tempfile
from unittest.mock import patch

import pytest
import click

from app.quick_edit import QuickEditor


def test_editor_command_injection():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            editor.edit_text_in_editor("test content")

        mock_run.assert_called_once_with("test content", editor="nano -w -K", require_save=True)


def test_editor_invalid_shell_syntax_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": '"unterminated'}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


def test_editor_denylist_execution_wrappers_blocked():
    editor = QuickEditor()

    forbidden_editors = [
        "bash -c 'malicious command'",
        "env python -c 'import os; os.system(\"id\")'",
        "python3 -c 'print(\"hello\")'",
        "/bin/sh -c 'echo pwned'",
        "cmd.exe /c calc.exe",
        "python3.12 -c 'print(\"hello\")'",
        '"C:\\Windows\\System32\\cmd.exe" /c calc',
        "pypy3 -c 'test'",
    ]

    for malicious_editor in forbidden_editors:
        with patch("click.edit") as mock_run:
            with patch.dict(os.environ, {"EDITOR": malicious_editor}):
                result = editor.edit_text_in_editor("test content")

        assert result is None, f"Expected {malicious_editor} to be blocked"
        mock_run.assert_not_called()


def test_editor_empty_command_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "   "}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


@pytest.mark.parametrize(
    "editor_value",
    [
        "nano ; whoami",
        "vim | cat /etc/passwd",
        "code && echo pwned",
        '"C:\\Program Files\\VS Code\\Code.exe" & calc.exe',
    ],
)
def test_editor_shell_metacharacters_are_rejected_before_execution(editor_value):
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": editor_value}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


def test_editor_handles_quoted_windows_paths():
    editor = QuickEditor()
    with patch("os.name", "nt"):
        with patch("click.edit") as mock_run:
            with patch.dict(
                os.environ, {"EDITOR": '"C:\\Program Files\\VS Code\\Code.exe" --wait'}
            ):
                editor.edit_text_in_editor("test content")

        mock_run.assert_called_once_with(
            "test content",
            editor='"C:\\Program Files\\VS Code\\Code.exe" --wait',
            require_save=True,
        )


def test_editor_non_mocked_denylist_execution_wrappers_blocked():
    """Non-mocked test proving that denylisted execution wrappers never reach click.edit.

    If they did reach click.edit, it would attempt to execute them. By verifying they return None
    immediately without mocking click.edit, we prove validation blocks them before execution.
    """
    editor = QuickEditor()
    forbidden_editors = [
        "bash -c 'malicious command'",
        "env python -c 'import os; os.system(\"id\")'",
        "python3 -c 'print(\"hello\")'",
        "/bin/sh -c 'echo pwned'",
        "cmd.exe /c calc.exe",
        "powershell -Command calc",
    ]

    for malicious in forbidden_editors:
        parts = editor._parse_editor_command(malicious)
        assert parts is None, f"Expected {malicious} to be blocked by parser"

        with patch.dict(os.environ, {"EDITOR": malicious}):
            # No mock on click.edit. If validation failed, it would try to execute.
            result = editor.edit_text_in_editor("test content")
            assert result is None


def test_editor_non_mocked_integration():
    """Non-mocked integration test using a temporary python script acting as an editor.

    Verifies that quick_edit correctly spawns the editor, passes the temp file,
    reads the modified content, and cleans up.
    """
    editor = QuickEditor()

    # Create a temporary python script acting as the editor
    editor_code = """import sys
if len(sys.argv) > 1:
    filepath = sys.argv[-1]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('integrated edited content')
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(editor_code)
        script_path = f.name.replace("\\", "/")

    try:
        if os.name == "nt":
            # On Windows, we invoke py launcher since it's not in the denylist
            editor_env = f'py "{script_path}"'
        else:
            # On Unix, we make the script executable and add a shebang
            os.chmod(script_path, 0o755)
            # Re-write with shebang to be safe
            with open(script_path, "w", encoding="utf-8") as f_rewrite:
                f_rewrite.write("#!/usr/bin/env python\n" + editor_code)
            editor_env = f'"{script_path}"'

        with patch.dict(os.environ, {"EDITOR": editor_env}):
            # Call without mocking click.edit
            result = editor.edit_text_in_editor("original content")

        assert result is not None
        assert result.strip() == "integrated edited content"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def test_editor_cancel_returns_none():
    """Verify that when click.edit returns None (cancel/no-save), edit_text_in_editor returns None."""
    editor = QuickEditor()
    with patch("click.edit", return_value=None) as mock_edit:
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None
    mock_edit.assert_called_once()


def test_editor_failure_returns_none():
    """Verify that editor failure/exception returns None, not the original text."""
    editor = QuickEditor()

    # ClickException
    with patch("click.edit", side_effect=click.ClickException("Editor failed")):
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None

    # Generic Exception
    with patch("click.edit", side_effect=Exception("Unexpected crash")):
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None


from unittest.mock import MagicMock


class MockEntry:
    def __init__(self, prompt_id, prompt_text, domain="general", language="en", tags=None):
        self.id = prompt_id
        self.prompt_text = prompt_text
        self.domain = domain
        self.language = language
        self.tags = tags or []
        self.score = 0.8
        self.notes = "notes"

    def to_dict(self):
        return {
            "id": self.id,
            "prompt_text": self.prompt_text,
            "domain": self.domain,
            "language": self.language,
            "tags": self.tags,
            "score": self.score,
            "notes": self.notes,
        }


def test_get_quick_editor_singleton():
    from app.quick_edit import get_quick_editor

    inst1 = get_quick_editor()
    inst2 = get_quick_editor()
    assert inst1 is inst2


def test_quick_editor_find_prompt():
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    h_entry = MockEntry("h1", "history text")
    f_entry = MockEntry("f1", "favorites text")

    editor.history_manager.get_by_id.side_effect = lambda x: h_entry if x == "h1" else None
    editor.favorites_manager.get_by_id.side_effect = lambda x: f_entry if x == "f1" else None

    # Find in history
    p, src = editor.find_prompt("h1")
    assert p["prompt_text"] == "history text"
    assert src == "history"

    # Find in favorites
    p, src = editor.find_prompt("f1")
    assert p["prompt_text"] == "favorites text"
    assert src == "favorites"

    # Not found
    p, src = editor.find_prompt("nonexistent")
    assert p is None
    assert src is None


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_prompt_no_changes(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    entry = MockEntry("h1", "hello")
    editor.history_manager.get_by_id.return_value = entry

    # Choice 1, confirm edit, but editor returns original content -> no changes
    mock_ask.side_effect = ["1"]
    mock_confirm.return_value = True
    with patch.object(editor, "edit_text_in_editor", return_value="hello"):
        res = editor.edit_prompt("h1")
        assert res is False


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_prompt_text_external_editor(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    entry = MockEntry("h1", "hello")
    editor.history_manager.get_by_id.return_value = entry
    editor.history_manager.entries = [entry]

    # Choice 1, confirm edit, editor returns new text
    mock_ask.side_effect = ["1"]
    mock_confirm.return_value = True
    with patch.object(editor, "edit_text_in_editor", return_value="hello modified"):
        res = editor.edit_prompt("h1")
        assert res is True
        assert entry.prompt_text == "hello modified"
        editor.history_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_prompt_text_manual(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    editor.history_manager.get_by_id.return_value = None
    entry = MockEntry("f1", "hello")
    editor.favorites_manager.get_by_id.return_value = entry
    editor.favorites_manager.entries = [entry]

    # Choice 1, manual entry (confirm=False), enter new text
    mock_ask.side_effect = ["1", "hello manually modified"]
    mock_confirm.return_value = False

    res = editor.edit_prompt("f1")
    assert res is True
    assert entry.prompt_text == "hello manually modified"
    editor.favorites_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
def test_edit_prompt_domain_and_language(mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    entry = MockEntry("h1", "hello", domain="general", language="en")
    editor.history_manager.get_by_id.return_value = entry
    editor.history_manager.entries = [entry]

    # Choice 2, enter new domain and language
    mock_ask.side_effect = ["2", "tech", "tr"]

    res = editor.edit_prompt("h1")
    assert res is True
    assert entry.domain == "tech"
    assert entry.language == "tr"
    editor.history_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
def test_edit_prompt_tags(mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    entry = MockEntry("h1", "hello", tags=["tag1"])
    editor.history_manager.get_by_id.return_value = entry
    editor.history_manager.entries = [entry]

    # Choice 3, enter new tags
    mock_ask.side_effect = ["3", "tag1, tag2, tag3"]

    res = editor.edit_prompt("h1")
    assert res is True
    assert entry.tags == ["tag1", "tag2", "tag3"]
    editor.history_manager._save.assert_called_once()


def test_edit_prompt_not_found(capsys):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()
    editor.history_manager.get_by_id.return_value = None
    editor.favorites_manager.get_by_id.return_value = None

    res = editor.edit_prompt("nonexistent")
    assert res is False
    captured = capsys.readouterr()
    assert "Prompt not found" in captured.out


def test_display_prompt_preview(capsys):
    editor = QuickEditor()
    prompt = {
        "id": "p1",
        "timestamp": "2026",
        "domain": "coding",
        "language": "en",
        "tags": ["test"],
        "input_text": "input text",
        "output_prompt": "output text",
    }
    editor.display_prompt_preview(prompt, "history")
    captured = capsys.readouterr()
    assert "history" in captured.out
    assert "coding" in captured.out
    assert "Input Text" in captured.out
    assert "Output Prompt" in captured.out
