import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import OptimizationRun


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

        # Add timestamp if we want? Or rely on filesystem
        # For now, just dump the model
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
            return OptimizationRun.model_validate(data)
        except Exception as e:
            print(f"Error loading run {run_id}: {e}")
            return None

    def list_runs(self) -> List[dict]:
        """
        List all available runs with basic metadata.
        Returns a list of dicts with {id, date, best_score, best_model}
        """
        runs = []
        for file_path in self.history_dir.glob("*.json"):
            try:
                # We could optimize this by having an index.json,
                # but for <1000 runs, reading files is fine if we're lazy loading
                # or just reading basic stats. For speed, let's just use file stats for date
                # and maybe peek at content if needed.
                # Actually, let's load them for now, assuming they aren't massive.
                # Optimization: In future, use index or separate meta file.

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                run = OptimizationRun.model_validate(data)

                # Timestamp from file mtime
                mtime = file_path.stat().st_mtime
                timestamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                runs.append(
                    {
                        "id": run.id,
                        "date": timestamp,
                        "generations": len(run.generations),
                        "best_score": run.best_candidate.score if run.best_candidate else 0.0,
                        "model": run.config.model,
                        "file_path": str(file_path),
                    }
                )
            except Exception:
                continue

        # Sort by date desc
        runs.sort(key=lambda x: x["date"], reverse=True)
        return runs
