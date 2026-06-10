from unittest.mock import patch

from app.quick_edit import QuickEditor


def test_editor_uses_click_edit():
    editor = QuickEditor()

    with patch("click.edit") as mock_edit:
        mock_edit.return_value = "edited content"
        result = editor.edit_text_in_editor("test content")

    mock_edit.assert_called_once_with("test content")
    assert result == "edited content"
