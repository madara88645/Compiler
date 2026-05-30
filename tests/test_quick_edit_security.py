import os
from unittest.mock import patch

from app.quick_edit import QuickEditor


def test_editor_invokes_click_edit():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = "edited text"
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once_with(
            "test content", editor="nano -w -K", extension=".txt", require_save=True
        )
        assert result == "edited text"


def test_editor_click_edit_returns_none_on_error():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.side_effect = Exception("Editor failed to launch")
        with patch.dict(os.environ, {"EDITOR": "invalid_editor"}):
            result = editor.edit_text_in_editor("test content")

        assert result is None
