from typer.testing import CliRunner
from datetime import datetime, timedelta

from app.history import HistoryEntry, HistoryManager
from cli.main import app


runner = CliRunner()


def test_history_cli_reads_real_sqlite_store(tmp_path, monkeypatch):
    manager = HistoryManager(str(tmp_path / "history.db"))
    manager.save(
        HistoryEntry(
            id="optimizer-entry",
            prompt_text="Explain bounded retry budgets",
            source="evolution",
            score=91.0,
            metadata={"run_id": "run-1"},
        )
    )
    monkeypatch.setattr("cli.commands.analytics.get_history_manager", lambda: manager)

    list_result = runner.invoke(app, ["history", "list"])
    search_result = runner.invoke(app, ["history", "search", "bounded"])
    show_result = runner.invoke(app, ["history", "show", "optimizer-entry"])
    stats_result = runner.invoke(app, ["history", "stats"])

    assert list_result.exit_code == 0, list_result.exception
    assert search_result.exit_code == 0, search_result.exception
    assert show_result.exit_code == 0, show_result.exception
    assert stats_result.exit_code == 0, stats_result.exception
    assert "Explain bounded retry budgets" in list_result.stdout
    assert "optimizer-entry" in show_result.stdout
    assert "evolution" in show_result.stdout
    assert "Explain bounded retry budgets" in show_result.stdout
    assert "Total Entries: 1" in stats_result.stdout


def test_history_cli_json_serializes_real_entries(tmp_path, monkeypatch):
    manager = HistoryManager(str(tmp_path / "history.db"))
    manager.save(HistoryEntry(id="json-entry", prompt_text="JSON history"))
    monkeypatch.setattr("cli.commands.analytics.get_history_manager", lambda: manager)

    result = runner.invoke(app, ["history", "list", "--json"])

    assert result.exit_code == 0, result.exception
    assert '"id": "json-entry"' in result.stdout


def test_history_cli_source_filter_applies_before_limit(tmp_path, monkeypatch):
    manager = HistoryManager(str(tmp_path / "history.db"))
    base = datetime(2026, 8, 25, 10, 0, 0)
    manager.save(
        HistoryEntry(
            id="latest-user",
            prompt_text="Latest user prompt",
            source="user",
            timestamp=base,
        )
    )
    manager.save(
        HistoryEntry(
            id="older-evolution",
            prompt_text="Evolution prompt that should still appear",
            source="evolution",
            timestamp=base - timedelta(minutes=1),
        )
    )
    monkeypatch.setattr("cli.commands.analytics.get_history_manager", lambda: manager)

    result = runner.invoke(app, ["history", "list", "--source", "evolution", "--limit", "1"])

    assert result.exit_code == 0, result.exception
    assert "evolution" in result.stdout
    assert "Evolution prompt that should still appear" in result.stdout
