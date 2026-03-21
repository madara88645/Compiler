import os
from unittest.mock import patch, MagicMock
from app.quick_edit import get_quick_editor


def test_edit_text_in_editor_with_args():
    editor_instance = get_quick_editor()

    with patch.dict(os.environ, {"EDITOR": "code --wait"}):
        with patch("subprocess.run") as mock_run:
            # Mock successful editor execution
            mock_run.return_value = MagicMock(returncode=0)

            # Use patch to avoid writing to an actual file and freezing during testing
            with patch("builtins.open") as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = "edited content"
                mock_open.return_value.__enter__.return_value = mock_file
                mock_open.return_value.__exit__.return_value = False

                with patch("tempfile.NamedTemporaryFile") as mock_temp:
                    mock_temp_file = MagicMock()
                    mock_temp_file.name = "mock_temp_path.txt"
                    mock_temp.return_value.__enter__.return_value = mock_temp_file
                    mock_temp.return_value.__exit__.return_value = False

                    # We also mock os.unlink to prevent trying to delete a non-existent file
                    with patch("os.unlink"):
                        result = editor_instance.edit_text_in_editor("original text")

                        # Verify the result is what we mocked the file to contain
                        assert result == "edited content"

                        # Verify subprocess.run was called correctly with args split
                        mock_run.assert_called_once_with(["code", "--wait", "mock_temp_path.txt"])


def test_edit_text_in_editor_rejects_invalid_editor_syntax():
    editor_instance = get_quick_editor()

    with patch.dict(os.environ, {"EDITOR": '"unterminated'}):
        with patch("subprocess.run") as mock_run:
            with patch("os.unlink"):
                result = editor_instance.edit_text_in_editor("original text")

    assert result is None
    mock_run.assert_not_called()


def test_edit_text_in_editor_rejects_empty_editor_command():
    editor_instance = get_quick_editor()

    with patch.dict(os.environ, {"EDITOR": "   "}):
        with patch("subprocess.run") as mock_run:
            with patch("os.unlink"):
                result = editor_instance.edit_text_in_editor("original text")

    assert result is None
    mock_run.assert_not_called()
