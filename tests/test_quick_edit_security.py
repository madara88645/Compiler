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


def test_editor_denylist_execution_wrappers_blocked():
    editor = QuickEditor()

    # Test that forbidden shells/interpreters are blocked, including common
    # bypass variants such as version-suffixed interpreters and Windows paths.
    forbidden_editors = [
        "bash -c 'malicious command'",
        "env python -c 'import os; os.system(\"id\")'",
        "python3 -c 'print(\"hello\")'",
        "python3.12 -c 'print(\"hello\")'",
        "python3.11 -c 'print(\"hello\")'",
        "pypy3 -c 'print(\"hello\")'",
        "/bin/sh -c 'echo pwned'",
        "dash -c 'echo pwned'",
        "fish -c 'echo pwned'",
        "tcsh -c 'echo pwned'",
        "cmd.exe /c calc.exe",
        r"C:\Windows\System32\cmd.exe /c calc.exe",
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


def test_editor_denylist_does_not_block_prefix_sharing_editors():
    """Editors whose names start with a forbidden prefix but have a non-version
    suffix (e.g. 'phpstorm', 'perlfect') must NOT be blocked, to avoid false
    positives from the prefix-based denylist."""
    editor = QuickEditor()

    # These names share a prefix with a forbidden interpreter but are legitimate
    # editor names; they should be passed through to subprocess.run.
    allowed_editors = [
        "phpstorm",
        "perlfect",
        "rubyx-edit",
    ]

    for allowed_editor in allowed_editors:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            with patch("builtins.open", create=True):
                with patch.dict(os.environ, {"EDITOR": allowed_editor}):
                    # We don't care about the return value; only that subprocess.run
                    # was called (i.e., the editor was not blocked).
                    editor.edit_text_in_editor("test content")

        mock_run.assert_called_once(), f"Expected {allowed_editor} to be allowed"
