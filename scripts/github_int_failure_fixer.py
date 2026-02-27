#!/usr/bin/env python3
"""GitHub Actions failure monitor and remediation helper.

This script polls failed workflow runs, inspects logs for known failure signatures,
and can optionally re-run failed jobs after surfacing actionable recommendations.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class WorkflowRunFailure:
    run_id: int
    workflow_name: str
    html_url: str
    head_branch: str
    conclusion: str
    recommendation: str
    signature: str


class GitHubActionsFailureFixer:
    """Detects GitHub Actions failures and optionally triggers run reruns."""

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        workflow_id: str | None = None,
        poll_seconds: int = 0,
        auto_rerun: bool = False,
        run_limit: int = 20,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.workflow_id = workflow_id
        self.token = token
        self.poll_seconds = poll_seconds
        self.auto_rerun = auto_rerun
        self.run_limit = run_limit

    @property
    def _base(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        request = Request(url=url, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "github-int-failure-fixer")

        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
                if not payload:
                    return {}
                return json.loads(payload)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API call failed ({exc.code}) for {method} {url}: {body}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Network error for {method} {url}: {exc}") from exc

    def _request_bytes(self, method: str, path: str) -> bytes:
        url = f"{self._base}{path}"
        request = Request(url=url, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "github-int-failure-fixer")
        with urlopen(request, timeout=60) as response:
            return response.read()

    def fetch_failed_runs(self) -> list[dict[str, Any]]:
        path = f"/actions/workflows/{self.workflow_id}/runs" if self.workflow_id else "/actions/runs"
        data = self._request(
            "GET",
            path,
            params={
                "status": "completed",
                "per_page": str(self.run_limit),
            },
        )
        runs = data.get("workflow_runs", [])
        return [run for run in runs if run.get("conclusion") == "failure"]

    def fetch_logs_text(self, run_id: int) -> str:
        archive = self._request_bytes("GET", f"/actions/runs/{run_id}/logs")
        zipped = zipfile.ZipFile(io.BytesIO(archive))
        chunks: list[str] = []
        for name in zipped.namelist():
            with zipped.open(name) as handle:
                chunks.append(handle.read().decode("utf-8", errors="replace"))
        return "\n".join(chunks)

    def analyze_failure(self, logs: str) -> tuple[str, str]:
        signatures = [
            (r"unable to find package\.json", "Node.js step expects package.json. Add it or skip Node steps."),
            (r"No such file or directory", "Workflow references missing files/paths. Verify checkout path and artifacts."),
            (r"ModuleNotFoundError", "Python dependency missing. Install required package in workflow setup step."),
            (r"npm ERR!", "npm dependency/build issue. Validate lockfile and install command."),
            (r"Authentication failed|permission denied|403", "Auth/permission issue. Verify token scope and secret mapping."),
            (r"Connection timed out|ECONNREFUSED", "Network/service availability issue. Check service startup and endpoint URLs."),
        ]

        for pattern, recommendation in signatures:
            if re.search(pattern, logs, flags=re.IGNORECASE):
                return pattern, recommendation

        return (
            "unknown",
            "No known failure signature matched. Review run logs and failing step output for context.",
        )

    def rerun_failed_jobs(self, run_id: int) -> None:
        self._request("POST", f"/actions/runs/{run_id}/rerun-failed-jobs")

    def monitor_once(self) -> list[WorkflowRunFailure]:
        failures: list[WorkflowRunFailure] = []
        runs = self.fetch_failed_runs()
        for run in runs:
            run_id = int(run["id"])
            logs = self.fetch_logs_text(run_id)
            signature, recommendation = self.analyze_failure(logs)
            failure = WorkflowRunFailure(
                run_id=run_id,
                workflow_name=run.get("name", "unknown"),
                html_url=run.get("html_url", ""),
                head_branch=run.get("head_branch", ""),
                conclusion=run.get("conclusion", ""),
                recommendation=recommendation,
                signature=signature,
            )
            failures.append(failure)

            if self.auto_rerun:
                self.rerun_failed_jobs(run_id)

        return failures

    def monitor(self) -> None:
        while True:
            failures = self.monitor_once()
            if failures:
                print_failure_report(failures)
            else:
                print("No failed workflow runs found.")

            if self.poll_seconds <= 0:
                break
            time.sleep(self.poll_seconds)


def print_failure_report(failures: list[WorkflowRunFailure]) -> None:
    print(f"Found {len(failures)} failed run(s):")
    for failure in failures:
        print("-" * 72)
        print(f"Run ID:         {failure.run_id}")
        print(f"Workflow:       {failure.workflow_name}")
        print(f"Branch:         {failure.head_branch}")
        print(f"Conclusion:     {failure.conclusion}")
        print(f"Signature:      {failure.signature}")
        print(f"Recommendation: {failure.recommendation}")
        print(f"URL:            {failure.html_url}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub Actions failure diagnosis + optional rerun tool")
    parser.add_argument("--owner", default=os.getenv("GITHUB_OWNER"), help="Repository owner/org")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPO"), help="Repository name")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN"), help="GitHub token")
    parser.add_argument("--workflow-id", default=os.getenv("GITHUB_WORKFLOW_ID"), help="Workflow ID or file name")
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.getenv("GITHUB_POLL_SECONDS", "0")),
        help="Poll interval in seconds (0 = run once)",
    )
    parser.add_argument(
        "--auto-rerun",
        action="store_true",
        default=os.getenv("GITHUB_AUTO_RERUN", "false").lower() == "true",
        help="Automatically trigger rerun for failed jobs",
    )
    parser.add_argument(
        "--run-limit",
        type=int,
        default=int(os.getenv("GITHUB_RUN_LIMIT", "20")),
        help="Number of recent runs to inspect",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    missing = [name for name, value in (("owner", args.owner), ("repo", args.repo), ("token", args.token)) if not value]
    if missing:
        print(f"Missing required options: {', '.join(missing)}", file=sys.stderr)
        return 2

    fixer = GitHubActionsFailureFixer(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        workflow_id=args.workflow_id,
        poll_seconds=args.poll_seconds,
        auto_rerun=args.auto_rerun,
        run_limit=args.run_limit,
    )
    fixer.monitor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
