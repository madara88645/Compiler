"""GitHub Actions failure fixer agent.

Monitors failed workflow runs, analyzes log text for common causes,
and can optionally trigger reruns for failed jobs.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class FailureRecommendation:
    pattern: re.Pattern[str]
    root_cause: str
    recommendation: str


RECOMMENDATIONS = [
    FailureRecommendation(
        pattern=re.compile(r"unable to find package\.json|ENOENT.*package\.json", re.IGNORECASE),
        root_cause="Node job executed in a directory without package.json.",
        recommendation=(
            "Set the correct working-directory for npm steps, or guard the Node job so it only runs "
            "when package.json exists."
        ),
    ),
    FailureRecommendation(
        pattern=re.compile(r"No module named|ModuleNotFoundError", re.IGNORECASE),
        root_cause="Python dependency missing in workflow environment.",
        recommendation="Install required packages before tests/lint and verify requirements lockstep.",
    ),
    FailureRecommendation(
        pattern=re.compile(r"permission denied|Resource not accessible by integration", re.IGNORECASE),
        root_cause="Insufficient token or workflow permissions.",
        recommendation="Update workflow permissions block and ensure required repo/token scopes are granted.",
    ),
]


class GitHubIntFailureFixer:
    def __init__(self, owner: str, repo: str, token: str, *, session: requests.Session | None = None) -> None:
        self.owner = owner
        self.repo = repo
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}{path}"

    def list_failed_runs(self, *, per_page: int = 10) -> list[dict[str, Any]]:
        response = self.session.get(
            self._url("/actions/runs"),
            params={"status": "completed", "conclusion": "failure", "per_page": per_page},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("workflow_runs", [])

    def download_run_logs(self, run_id: int) -> str:
        response = self.session.get(self._url(f"/actions/runs/{run_id}/logs"), timeout=60)
        response.raise_for_status()

        zip_bytes = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_bytes) as log_archive:
            collected: list[str] = []
            for name in log_archive.namelist():
                if not name.endswith(".txt"):
                    continue
                with log_archive.open(name) as file_obj:
                    collected.append(file_obj.read().decode("utf-8", errors="replace"))
            return "\n".join(collected)

    def analyze_failure(self, log_text: str) -> tuple[str, str]:
        for item in RECOMMENDATIONS:
            if item.pattern.search(log_text):
                return item.root_cause, item.recommendation
        return (
            "Unknown failure signature.",
            "Inspect job logs for stack traces, then add a signature rule for automated diagnosis.",
        )

    def rerun_failed_jobs(self, run_id: int) -> None:
        response = self.session.post(self._url(f"/actions/runs/{run_id}/rerun-failed-jobs"), timeout=30)
        response.raise_for_status()

    def process_failed_runs(self, *, auto_rerun: bool, dry_run: bool) -> list[dict[str, Any]]:
        failed_runs = self.list_failed_runs()
        reports: list[dict[str, Any]] = []

        for run in failed_runs:
            run_id = run["id"]
            logs = self.download_run_logs(run_id)
            root_cause, recommendation = self.analyze_failure(logs)
            rerun_status = "skipped"

            if auto_rerun and not dry_run:
                self.rerun_failed_jobs(run_id)
                rerun_status = "triggered"

            reports.append(
                {
                    "run_id": run_id,
                    "name": run.get("name"),
                    "html_url": run.get("html_url"),
                    "root_cause": root_cause,
                    "recommendation": recommendation,
                    "rerun_status": rerun_status,
                }
            )
        return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze and remediate failed GitHub Actions runs.")
    parser.add_argument("--owner", required=True, help="Repository owner/org")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN"), help="GitHub token (defaults to GITHUB_TOKEN)")
    parser.add_argument("--auto-rerun", action="store_true", help="Trigger rerun-failed-jobs API for failed runs")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only; do not change workflow run state")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token:
        raise SystemExit("A GitHub token is required via --token or GITHUB_TOKEN.")

    fixer = GitHubIntFailureFixer(args.owner, args.repo, args.token)
    report = fixer.process_failed_runs(auto_rerun=args.auto_rerun, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
