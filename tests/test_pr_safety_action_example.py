from pathlib import Path


def test_advisory_action_reuses_repo_aware_cli_path() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / "examples/github/pr-safety-advisory.yml").read_text(encoding="utf-8")

    assert "python -m cli.main pr-safety" in workflow
    assert "--from-git" in workflow
    assert "--format md" in workflow
    assert "from app.pr_safety.analyzer import analyze_pr_safety" not in workflow
