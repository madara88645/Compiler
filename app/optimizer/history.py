import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional

from .models import OptimizationRun

logger = logging.getLogger(__name__)


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize naive and aware datetimes for consistent storage and sorting."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class HistoryManager:
    """
    Manages the persistence of OptimizationRuns.
    Storage layout: ~/.promptc/history/runs/{run_id}.json
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.history_dir = base_dir / "history" / "runs"
        else:
            # Default to ~/.promptc/history/runs
            self.history_dir = Path.home() / ".promptc" / "history" / "runs"

        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run: OptimizationRun) -> Path:
        """Save a run to disk."""
        file_path = self.history_dir / f"{run.id}.json"
        if run.created_at is None:
            run.created_at = datetime.now(UTC).replace(microsecond=0)
        else:
            run.created_at = _normalize_datetime(run.created_at).replace(tzinfo=None)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(run.model_dump_json(indent=2))

        return file_path

    def load_run(self, run_id: str) -> Optional[OptimizationRun]:
        """Load a run by ID."""
        file_path = self.history_dir / f"{run_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            run = OptimizationRun.model_validate(data)
            if run.created_at is None:
                run.created_at = datetime.fromtimestamp(file_path.stat().st_mtime, UTC).replace(
                    tzinfo=None
                )
            return run
        except Exception as e:
            logger.warning("Error loading optimization run %s: %s", run_id, e)
            return None

    def list_runs(self) -> List[dict]:
        """
        List all available runs with basic metadata.
        Returns a list of dicts with {id, date, best_score, best_model}
        """
        runs = []
        for file_path in self.history_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                run = OptimizationRun.model_validate(data)
                created_at = run.created_at or datetime.fromtimestamp(
                    file_path.stat().st_mtime, UTC
                ).replace(tzinfo=None)

                runs.append(
                    {
                        "id": run.id,
                        "date": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "created_at": created_at,
                        "generations": len(run.generations),
                        "best_score": run.best_candidate.score if run.best_candidate else 0.0,
                        "model": run.config.model,
                        "file_path": str(file_path),
                    }
                )
            except Exception:
                continue

        runs.sort(key=lambda x: x["created_at"], reverse=True)
        for run in runs:
            run.pop("created_at", None)
        return runs
