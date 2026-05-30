import os
from unittest.mock import patch

from app.quick_edit import QuickEditor


def test_editor_command_injection():
    editor = QuickEditor()

    # Mock click.edit
    with patch("click.edit") as mock_edit:
        mock_edit.return_value = "edited content"
        # Simulate an environment variable with arguments
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            result = editor.edit_text_in_editor("test content")

        # click.edit should be called safely
        mock_edit.assert_called_once_with(text="test content", editor="nano -w -K")
        assert result == "edited content"


def test_editor_invalid_shell_syntax_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        # click.edit handles shell stuff internally, but we can mock it raising an exception
        # if the editor string is severely malformed.
        mock_edit.side_effect = Exception("Editing failed")
        with patch.dict(os.environ, {"EDITOR": '"unterminated'}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_edit.assert_called_once()


def test_editor_empty_command_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = None  # simulated no change
        with patch.dict(os.environ, {"EDITOR": "   "}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_edit.assert_called_once()
