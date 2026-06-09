import os
from unittest.mock import patch


from app.quick_edit import QuickEditor


def test_editor_click_edit_used():
    editor = QuickEditor()

    with patch("click.edit", return_value="edited content") as mock_edit:
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")

        mock_edit.assert_called_once_with("test content", editor="nano", extension=".txt")
        assert result == "edited content"


def test_editor_click_edit_handles_usage_error():
    editor = QuickEditor()
    import click

    with patch("click.edit", side_effect=click.UsageError("bad editor")):
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
