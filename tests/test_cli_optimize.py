import os
import site
from datetime import datetime
from pathlib import Path

import pytest

from app.optimizer.history import HistoryManager
from app.optimizer.models import Candidate, EvaluationResult, OptimizationConfig, OptimizationRun
from tests.test_cli_extras import run_cli


def _home_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    user_site = site.getusersitepackages()
    if user_site:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{user_site}{os.pathsep}{existing}" if existing else user_site
    env["HOME"] = str(tmp_path)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _write_optimize_inputs(work_dir: Path) -> tuple[Path, Path]:
    prompt_file = work_dir / "prompt.txt"
    suite_file = work_dir / "suite.yaml"
    prompt_file.write_text("Write a concise answer about {{topic}}.", encoding="utf-8")
    suite_file.write_text(
        """name: CLI Optimize Suite
prompt_file: prompt.txt
test_cases:
  - id: tc1
    input_variables:
      topic: testing
    assertions:
      - type: not_contains
        value: error
""",
        encoding="utf-8",
    )
    return prompt_file, suite_file


def _build_run(run_id: str, created_at: datetime | None = None) -> OptimizationRun:
    candidate = Candidate(
        generation=0,
        prompt_text="Write a concise answer about testing.",
        mutation_type="initial",
        result=EvaluationResult(
            score=0.75,
            passed_count=1,
            failed_count=0,
            error_count=0,
            avg_latency_ms=12.0,
            failures=[],
        ),
    )
    return OptimizationRun(
        id=run_id,
        config=OptimizationConfig(max_generations=1, model="mock-model"),
        created_at=created_at,
        generations=[[candidate]],
        best_candidate=candidate,
    )


def _seed_history(tmp_path: Path, run_id: str = "cli-opt-run-1") -> str:
    manager = HistoryManager(base_dir=tmp_path / ".promptc")
    manager.save_run(_build_run(run_id, datetime(2024, 4, 5, 6, 7, 8)))
    return run_id


def test_optimize_run_dry_run_with_mock_provider(tmp_path: Path):
    work_dir = tmp_path / "optimize-inputs"
    work_dir.mkdir()
    prompt_file, suite_file = _write_optimize_inputs(work_dir)

    code, out, err = run_cli(
        [
            "optimize",
            "run",
            str(prompt_file),
            str(suite_file),
            "--dry-run",
            "--provider",
            "mock",
            "--generations",
            "2",
        ],
        Path.cwd(),
        env=_home_env(tmp_path),
    )

    assert code == 0, f"stdout={out}\nstderr={err}"
    assert "Running Cost Estimation" in out
    assert "Dry Run Estimate" in out


def test_optimize_resume_with_mock_provider(tmp_path: Path):
    work_dir = tmp_path / "optimize-inputs"
    work_dir.mkdir()
    prompt_file, suite_file = _write_optimize_inputs(work_dir)
    run_id = _seed_history(tmp_path)

    code, out, err = run_cli(
        [
            "optimize",
            "resume",
            run_id,
            "--suite",
            str(suite_file),
            "--provider",
            "mock",
            "--generations",
            "1",
        ],
        Path.cwd(),
        env=_home_env(tmp_path),
    )

    assert code == 0, f"stdout={out}\nstderr={err}"
    assert "Using mock provider" in out
    assert f"Resuming Run {run_id}" in out
    assert "Optimization Complete!" in out
    assert "Best Score:" in out


def test_optimize_history_list_with_mock_provider(tmp_path: Path):
    run_id = _seed_history(tmp_path)

    code, out, err = run_cli(
        ["optimize", "history", "list", "--limit", "5"],
        Path.cwd(),
        env=_home_env(tmp_path),
    )

    assert code == 0, f"stdout={out}\nstderr={err}"
    assert "Optimization History" in out
    assert run_id[:8] in out
    assert "2024-04-05 06:07:08" in out


def test_optimize_history_show_with_mock_provider(tmp_path: Path):
    run_id = _seed_history(tmp_path)

    code, out, err = run_cli(
        ["optimize", "history", "show", run_id],
        Path.cwd(),
        env=_home_env(tmp_path),
    )

    assert code == 0, f"stdout={out}\nstderr={err}"
    assert f"Run Details: {run_id}" in out
    assert "Date: 2024-04-05 06:07:08" in out
    assert "Write a concise answer about testing." in out
