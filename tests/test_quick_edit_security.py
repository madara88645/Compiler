import os
from unittest.mock import patch
from app.quick_edit import QuickEditor


def test_editor_calls_click_edit():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = "modified text"
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once_with("test content", require_save=False)
        assert result == "modified text"
