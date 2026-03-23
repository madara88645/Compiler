import os
from unittest.mock import patch

from app.quick_edit import QuickEditor


def test_editor_command_injection():
    editor = QuickEditor()

    # Mock subprocess.run
    with patch("subprocess.run") as mock_run:
        # Simulate an environment variable with arguments
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            editor.edit_text_in_editor("test content")

        # subprocess.run should receive a list of arguments, correctly split
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "nano"
        assert args[1] == "-w"
        assert args[2] == "-K"
        # The last argument should be the temp file path
        assert args[3].endswith(".txt")


def test_editor_invalid_shell_syntax_returns_none():
    editor = QuickEditor()

    with patch("subprocess.run") as mock_run:
        with patch.dict(os.environ, {"EDITOR": '"unterminated'}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


def test_editor_empty_command_returns_none():
    editor = QuickEditor()

    with patch("subprocess.run") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "   "}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()
