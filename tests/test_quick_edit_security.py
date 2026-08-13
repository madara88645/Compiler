# ruff: noqa: E402
from unittest.mock import patch, MagicMock

import click

from app.history import HistoryEntry, HistoryManager
from app.quick_edit import QuickEditor


def test_editor_cancel_returns_none():
    """Verify that when click.edit returns None (cancel/no-save), edit_text_in_editor returns None."""
    editor = QuickEditor()
    with patch("click.edit", return_value=None) as mock_edit:
        result = editor.edit_text_in_editor("test content")
    assert result is None
    mock_edit.assert_called_once()


def test_editor_failure_returns_none():
    """Verify that editor failure/exception returns None, not the original text."""
    editor = QuickEditor()

    # ClickException
    with patch("click.edit", side_effect=click.ClickException("Editor failed")):
        result = editor.edit_text_in_editor("test content")
    assert result is None

    # Generic Exception
    with patch("click.edit", side_effect=Exception("Unexpected crash")):
        result = editor.edit_text_in_editor("test content")
    assert result is None


def test_editor_success_returns_edited_content_and_requires_save():
    """Verify the safe Click editor path returns saved content and requires an explicit save."""
    editor = QuickEditor()

    with patch("click.edit", return_value="edited content") as mock_edit:
        result = editor.edit_text_in_editor("test content")

    assert result == "edited content"
    mock_edit.assert_called_once_with("test content", require_save=True)


class MockEntry:
    def __init__(self, prompt_id, prompt_text, domain="general", language="en", tags=None):
        self.id = prompt_id
        self.prompt_text = prompt_text
        self.domain = domain
        self.language = language
        self.tags = tags or []
        self.score = 0.8
        self.notes = "notes"

    def to_dict(self):
        return {
            "id": self.id,
            "prompt_text": self.prompt_text,
            "domain": self.domain,
            "language": self.language,
            "tags": self.tags,
            "score": self.score,
            "notes": self.notes,
        }


def test_get_quick_editor_singleton():
    from app.quick_edit import get_quick_editor

    inst1 = get_quick_editor()
    inst2 = get_quick_editor()
    assert inst1 is inst2


def test_quick_editor_find_prompt_reads_real_history_store(tmp_path, monkeypatch):
    history_manager = HistoryManager(str(tmp_path / "history.db"))
    history_manager.save(
        HistoryEntry(
            id="h1",
            prompt_text="history text",
            source="evolution",
            metadata={"run_id": "run-1"},
        )
    )

    monkeypatch.setattr("app.quick_edit.get_history_manager", lambda: history_manager)
    editor = QuickEditor()
    editor.favorites_manager = MagicMock()

    f_entry = MockEntry("f1", "favorites text")

    editor.favorites_manager.get_by_id.side_effect = lambda x: f_entry if x == "f1" else None

    # Find in history
    p, src = editor.find_prompt("h1")
    assert p["prompt_text"] == "history text"
    assert p["source"] == "evolution"
    assert src == "history"

    # Find in favorites
    p, src = editor.find_prompt("f1")
    assert p["prompt_text"] == "favorites text"
    assert src == "favorites"

    # Not found
    p, src = editor.find_prompt("nonexistent")
    assert p is None
    assert src is None


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_quick_editor_persists_history_text_edit(mock_confirm, mock_ask, tmp_path, monkeypatch):
    history_manager = HistoryManager(str(tmp_path / "history.db"))
    history_manager.save(HistoryEntry(id="h1", prompt_text="before"))
    monkeypatch.setattr("app.quick_edit.get_history_manager", lambda: history_manager)

    editor = QuickEditor()
    mock_ask.side_effect = ["1"]
    mock_confirm.return_value = True

    with patch.object(editor, "edit_text_in_editor", return_value="after"):
        assert editor.edit_prompt("h1") is True

    assert history_manager.get_by_id("h1").prompt_text == "after"


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_prompt_no_changes(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    entry = MockEntry("h1", "hello")
    editor.history_manager.get_by_id.return_value = entry

    # Choice 1, confirm edit, but editor returns original content -> no changes
    mock_ask.side_effect = ["1"]
    mock_confirm.return_value = True
    with patch.object(editor, "edit_text_in_editor", return_value="hello"):
        res = editor.edit_prompt("h1")
        assert res is False


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_favorite_text_external_editor(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    editor.history_manager.get_by_id.return_value = None
    entry = MockEntry("f1", "hello")
    editor.favorites_manager.get_by_id.return_value = entry
    editor.favorites_manager.entries = [entry]

    # Choice 1, confirm edit, editor returns new text
    mock_ask.side_effect = ["1"]
    mock_confirm.return_value = True
    with patch.object(editor, "edit_text_in_editor", return_value="hello modified"):
        res = editor.edit_prompt("f1")
        assert res is True
        assert entry.prompt_text == "hello modified"
        editor.favorites_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
@patch("rich.prompt.Confirm.ask")
def test_edit_prompt_text_manual(mock_confirm, mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    editor.history_manager.get_by_id.return_value = None
    entry = MockEntry("f1", "hello")
    editor.favorites_manager.get_by_id.return_value = entry
    editor.favorites_manager.entries = [entry]

    # Choice 1, manual entry (confirm=False), enter new text
    mock_ask.side_effect = ["1", "hello manually modified"]
    mock_confirm.return_value = False

    res = editor.edit_prompt("f1")
    assert res is True
    assert entry.prompt_text == "hello manually modified"
    editor.favorites_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
def test_edit_favorite_domain_and_language(mock_ask):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()

    editor.history_manager.get_by_id.return_value = None
    entry = MockEntry("f1", "hello", domain="general", language="en")
    editor.favorites_manager.get_by_id.return_value = entry
    editor.favorites_manager.entries = [entry]

    # Choice 2, enter new domain and language
    mock_ask.side_effect = ["2", "tech", "tr"]

    res = editor.edit_prompt("f1")
    assert res is True
    assert entry.domain == "tech"
    assert entry.language == "tr"
    editor.favorites_manager._save.assert_called_once()


@patch("rich.prompt.Prompt.ask")
def test_edit_history_tags(mock_ask, tmp_path, monkeypatch):
    history_manager = HistoryManager(str(tmp_path / "history.db"))
    history_manager.save(HistoryEntry(id="h1", prompt_text="hello", metadata={"tags": ["tag1"]}))
    monkeypatch.setattr("app.quick_edit.get_history_manager", lambda: history_manager)
    editor = QuickEditor()

    # Choice 3, enter new tags
    mock_ask.side_effect = ["3", "tag1, tag2, tag3"]

    res = editor.edit_prompt("h1")
    assert res is True
    assert history_manager.get_by_id("h1").metadata["tags"] == ["tag1", "tag2", "tag3"]


def test_edit_prompt_not_found(capsys):
    editor = QuickEditor()
    editor.history_manager = MagicMock()
    editor.favorites_manager = MagicMock()
    editor.history_manager.get_by_id.return_value = None
    editor.favorites_manager.get_by_id.return_value = None

    res = editor.edit_prompt("nonexistent")
    assert res is False
    captured = capsys.readouterr()
    assert "Prompt not found" in captured.out


def test_display_prompt_preview(capsys):
    editor = QuickEditor()
    prompt = {
        "id": "p1",
        "timestamp": "2026",
        "domain": "coding",
        "language": "en",
        "tags": ["test"],
        "input_text": "input text",
        "output_prompt": "output text",
    }
    editor.display_prompt_preview(prompt, "history")
    captured = capsys.readouterr()
    assert "history" in captured.out
    assert "coding" in captured.out
    assert "Input Text" in captured.out
    assert "Output Prompt" in captured.out
