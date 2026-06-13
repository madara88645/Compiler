import os
import tempfile
from unittest.mock import patch

import pytest
import click

from app.quick_edit import QuickEditor


def test_editor_command_injection():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "nano -w -K"}):
            editor.edit_text_in_editor("test content")

        mock_run.assert_called_once_with("test content", editor="nano -w -K", require_save=True)


def test_editor_invalid_shell_syntax_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": '"unterminated'}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


def test_editor_denylist_execution_wrappers_blocked():
    editor = QuickEditor()

    forbidden_editors = [
        "bash -c 'malicious command'",
        "env python -c 'import os; os.system(\"id\")'",
        "python3 -c 'print(\"hello\")'",
        "/bin/sh -c 'echo pwned'",
        "cmd.exe /c calc.exe",
        "python3.12 -c 'print(\"hello\")'",
        '"C:\\Windows\\System32\\cmd.exe" /c calc',
        "pypy3 -c 'test'",
    ]

    for malicious_editor in forbidden_editors:
        with patch("click.edit") as mock_run:
            with patch.dict(os.environ, {"EDITOR": malicious_editor}):
                result = editor.edit_text_in_editor("test content")

        assert result is None, f"Expected {malicious_editor} to be blocked"
        mock_run.assert_not_called()


def test_editor_empty_command_returns_none():
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": "   "}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


@pytest.mark.parametrize(
    "editor_value",
    [
        "nano ; whoami",
        "vim | cat /etc/passwd",
        "code && echo pwned",
        '"C:\\Program Files\\VS Code\\Code.exe" & calc.exe',
    ],
)
def test_editor_shell_metacharacters_are_rejected_before_execution(editor_value):
    editor = QuickEditor()

    with patch("click.edit") as mock_run:
        with patch.dict(os.environ, {"EDITOR": editor_value}):
            result = editor.edit_text_in_editor("test content")

    assert result is None
    mock_run.assert_not_called()


def test_editor_handles_quoted_windows_paths():
    editor = QuickEditor()
    with patch("os.name", "nt"):
        with patch("click.edit") as mock_run:
            with patch.dict(
                os.environ, {"EDITOR": '"C:\\Program Files\\VS Code\\Code.exe" --wait'}
            ):
                editor.edit_text_in_editor("test content")

        mock_run.assert_called_once_with(
            "test content",
            editor='"C:\\Program Files\\VS Code\\Code.exe" --wait',
            require_save=True,
        )


def test_editor_non_mocked_denylist_execution_wrappers_blocked():
    """Non-mocked test proving that denylisted execution wrappers never reach click.edit.

    If they did reach click.edit, it would attempt to execute them. By verifying they return None
    immediately without mocking click.edit, we prove validation blocks them before execution.
    """
    editor = QuickEditor()
    forbidden_editors = [
        "bash -c 'malicious command'",
        "env python -c 'import os; os.system(\"id\")'",
        "python3 -c 'print(\"hello\")'",
        "/bin/sh -c 'echo pwned'",
        "cmd.exe /c calc.exe",
        "powershell -Command calc",
    ]

    for malicious in forbidden_editors:
        parts = editor._parse_editor_command(malicious)
        assert parts is None, f"Expected {malicious} to be blocked by parser"

        with patch.dict(os.environ, {"EDITOR": malicious}):
            # No mock on click.edit. If validation failed, it would try to execute.
            result = editor.edit_text_in_editor("test content")
            assert result is None


def test_editor_non_mocked_integration():
    """Non-mocked integration test using a temporary python script acting as an editor.

    Verifies that quick_edit correctly spawns the editor, passes the temp file,
    reads the modified content, and cleans up.
    """
    editor = QuickEditor()

    # Create a temporary python script acting as the editor
    editor_code = """import sys
if len(sys.argv) > 1:
    filepath = sys.argv[-1]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('integrated edited content')
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(editor_code)
        script_path = f.name.replace("\\", "/")

    try:
        if os.name == "nt":
            # On Windows, we invoke py launcher since it's not in the denylist
            editor_env = f'py "{script_path}"'
        else:
            # On Unix, we make the script executable and add a shebang
            os.chmod(script_path, 0o755)
            # Re-write with shebang to be safe
            with open(script_path, "w", encoding="utf-8") as f_rewrite:
                f_rewrite.write("#!/usr/bin/env python\n" + editor_code)
            editor_env = f'"{script_path}"'

        with patch.dict(os.environ, {"EDITOR": editor_env}):
            # Call without mocking click.edit
            result = editor.edit_text_in_editor("original content")

        assert result is not None
        assert result.strip() == "integrated edited content"
    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


def test_editor_cancel_returns_none():
    """Verify that when click.edit returns None (cancel/no-save), edit_text_in_editor returns None."""
    editor = QuickEditor()
    with patch("click.edit", return_value=None) as mock_edit:
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None
    mock_edit.assert_called_once()


def test_editor_failure_returns_none():
    """Verify that editor failure/exception returns None, not the original text."""
    editor = QuickEditor()

    # ClickException
    with patch("click.edit", side_effect=click.ClickException("Editor failed")):
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None

    # Generic Exception
    with patch("click.edit", side_effect=Exception("Unexpected crash")):
        with patch.dict(os.environ, {"EDITOR": "nano"}):
            result = editor.edit_text_in_editor("test content")
    assert result is None
