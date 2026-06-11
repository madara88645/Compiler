import os
from unittest.mock import patch

import pytest

from app.quick_edit import QuickEditor


def test_editor_command_injection():
    editor = QuickEditor()

    with patch("subprocess.run") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            editor.edit_text_in_editor("test content")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "nano"
        assert args[1] == "-w"
        assert args[2] == "-K"
        assert args[3].endswith(".txt")


def test_editor_invalid_shell_syntax_returns_none():
    editor = QuickEditor()

    with patch("subprocess.run") as mock_run:
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
        with patch("subprocess.run") as mock_run:
            with patch.dict(os.environ, {"EDITOR": malicious_editor}):
                result = editor.edit_text_in_editor("test content")

        assert result is None, f"Expected {malicious_editor} to be blocked"
        mock_run.assert_not_called()


def test_editor_empty_command_returns_none():
    editor = QuickEditor()

    with patch("subprocess.run") as mock_run:
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

    with patch("subprocess.run") as mock_run:
        with patch.dict(os.environ, {"EDITOR": editor_value}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()
