from app.history import HistoryEntry, HistoryManager
from app.prompt_diff import PromptComparison
import uuid


def test_history_diff_integration(tmp_path):
    print("Testing History <-> Le Prompt Diff Integration...")

    # 1. Seed History
    history = HistoryManager(str(tmp_path / "history.db"))
    prompt_id = str(uuid.uuid4())
    entry = HistoryEntry(
        id=prompt_id,
        prompt_text="Hello History World",
        source="test",
        metadata={"note": "seeded for test"},
    )
    history.save(entry)
    print(f"Seeded prompt {prompt_id}")

    # 2. Use PromptComparison to retrieve it
    differ = PromptComparison.__new__(PromptComparison)
    differ.history = history
    success, text, source = differ.get_prompt_text(prompt_id, source="history")

    print(f"Retrieval result: success={success}, text='{text}', source='{source}'")

    assert success is True
    assert text == "Hello History World"
    assert source == "history"

    # 3. Diff against something else
    stats = differ.get_diff_stats(text, "Hello New World")
    print(f"Diff Stats: {stats}")

    assert stats["similarity"] > 0
    assert (
        stats["lines_same"] == 0
    )  # "Hello History World" vs "Hello New World" - actually difflib might find some commonality but lines are different?
    # Wait, splitlines() on single line string gives 1 line.
    # "Hello History World" vs "Hello New World"
    # difflib.SequenceMatcher on lists of lines.
    # They are different lines.

    print("✅ History Diff integration passed!")
