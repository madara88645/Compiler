import click
from unittest.mock import patch

from app.quick_edit import QuickEditor


def test_edit_text_in_editor_calls_click_edit():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = "edited content"
        result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once_with("test content", extension=".txt", require_save=False)
        assert result == "edited content"


def test_edit_text_in_editor_returns_none_on_cancel():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = None
        result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once()
        assert result is None


def test_edit_text_in_editor_handles_click_exception():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.side_effect = click.ClickException("Editor failed")
        result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once()
        assert result is None


def test_edit_text_in_editor_handles_general_exception():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.side_effect = Exception("General error")
        result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once()
        assert result is None
