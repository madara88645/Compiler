from datetime import datetime
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from app.optimizer.history import HistoryManager
from app.optimizer.models import Candidate, EvaluationResult, OptimizationConfig, OptimizationRun
from cli.commands.optimize import app
import cli.commands.optimize


runner = CliRunner()


def _build_run(run_id: str, created_at: datetime | None = None) -> OptimizationRun:
    candidate = Candidate(
        generation=0,
        prompt_text="Return concise answers.",
        mutation_type="initial",
        result=EvaluationResult(
            score=0.75,
            passed_count=3,
            failed_count=1,
            error_count=0,
            avg_latency_ms=12.0,
            failures=["One failed case"],
        ),
    )
    return OptimizationRun(
        id=run_id,
        config=OptimizationConfig(model="mock-model"),
        created_at=created_at,
        generations=[[candidate]],
        best_candidate=candidate,
    )


def test_history_manager_persists_created_at_and_sorts_runs(tmp_path):
    manager = HistoryManager(base_dir=tmp_path)
    older = _build_run("older-run", datetime(2024, 1, 2, 3, 4, 5))
    newer = _build_run("newer-run", datetime(2024, 2, 3, 4, 5, 6))

    manager.save_run(older)
    manager.save_run(newer)

    loaded = manager.load_run("older-run")
    runs = manager.list_runs()

    assert loaded is not None
    assert loaded.created_at == older.created_at
    assert [run["id"] for run in runs] == ["newer-run", "older-run"]
    assert runs[0]["date"] == "2024-02-03 04:05:06"


def test_history_manager_backfills_created_at_from_existing_file(tmp_path):
    manager = HistoryManager(base_dir=tmp_path)
    run = _build_run("legacy-run")
    file_path = manager.save_run(run)

    legacy_payload = run.model_dump()
    legacy_payload.pop("created_at", None)
    file_path.write_text(OptimizationRun.model_validate(legacy_payload).model_dump_json(indent=2), encoding="utf-8")

    loaded = manager.load_run("legacy-run")
    assert loaded is not None
    assert loaded.created_at is not None


def test_history_cli_list_and_show_use_saved_dates(tmp_path, monkeypatch):
    promptc_home = tmp_path / ".promptc"
    manager = HistoryManager(base_dir=promptc_home)
    run = _build_run("cli-run-1234", datetime(2024, 3, 4, 5, 6, 7))
    manager.save_run(run)

    original_console = cli.commands.optimize.console
    try:
        cli.commands.optimize.console = Console(force_terminal=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        list_result = runner.invoke(app, ["history", "list"])
        show_result = runner.invoke(app, ["history", "show", "cli-run-1234"])

        assert list_result.exit_code == 0
        assert show_result.exit_code == 0
        assert "Optimization History" in list_result.stdout
        assert "2024-03-04 05:06:07" in list_result.stdout
        assert "Run Details: cli-run-1234" in show_result.stdout
        assert "Date: 2024-03-04 05:06:07" in show_result.stdout
    finally:
        cli.commands.optimize.console = original_console
