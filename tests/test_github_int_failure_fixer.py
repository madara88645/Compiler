from scripts.github_int_failure_fixer import GitHubActionsFailureFixer


def build_fixer() -> GitHubActionsFailureFixer:
    return GitHubActionsFailureFixer(owner="o", repo="r", token="t")


def test_analyze_failure_detects_package_json_issue() -> None:
    pattern, recommendation = build_fixer().analyze_failure("Error: unable to find package.json in /workspace")
    assert "package\\.json" in pattern
    assert "package.json" in recommendation


def test_analyze_failure_returns_unknown_for_unmatched_log() -> None:
    pattern, recommendation = build_fixer().analyze_failure("completely novel error")
    assert pattern == "unknown"
    assert "No known failure signature" in recommendation
