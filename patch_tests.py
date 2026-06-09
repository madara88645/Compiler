import re

with open("tests/test_quick_edit_security.py", "r") as f:
    content = f.read()

# Since click.edit replaces subprocess.run, all the tests expecting subprocess.run
# or the manual denylist are no longer applicable. We should rewrite the test file
# to just verify that click.edit is called.

new_content = """import os
from unittest.mock import patch

import pytest

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
"""

with open("tests/test_quick_edit_security.py", "w") as f:
    f.write(new_content)
