from app.pr_safety.analyzer import analyze_pr_safety
from app.pr_safety.path_rules import top_level_directories


def test_docs_only_pr_recommends_merge():
    report = analyze_pr_safety(
        title="docs: update README",
        description="Document the new install steps for contributors.",
        changed_files=["README.md", "docs/contributing.md"],
    )

    assert report.verdict == "merge"
    assert report.changed_files.total == 2
    assert "docs" in {group.name for group in report.changed_files.groups}
    assert report.risky_areas.status == "ok"
    assert report.test_coverage.status == "ok"
    assert report.scope_match.status == "ok"
    assert any("Docs-only" in item for item in report.recommendations)


def test_auth_change_without_tests_recommends_hold():
    report = analyze_pr_safety(
        title="feat: add login flow",
        description="Add session-based login endpoints for the API.",
        changed_files=[
            "api/routes/auth.py",
            "app/models/user.py",
        ],
    )

    assert report.verdict == "hold"
    assert report.test_coverage.status == "gap"
    assert {gap.file for gap in report.test_coverage.gaps} == {
        "api/routes/auth.py",
        "app/models/user.py",
    }
    assert any(hit.category == "auth" for hit in report.risky_areas.hits)
    assert any("tests" in item.lower() for item in report.recommendations)


def test_env_file_change_flags_risky_area_and_hold():
    report = analyze_pr_safety(
        title="chore: update local env template",
        description="Refresh example environment variables for development.",
        changed_files=[".env.example", "README.md"],
    )

    assert report.verdict == "hold"
    assert any(hit.category == "secrets" for hit in report.risky_areas.hits)
    assert any(hit.file == ".env.example" for hit in report.risky_areas.hits)
    assert any("secret" in item.lower() for item in report.recommendations)


def test_many_files_across_directories_recommends_split():
    changed_files = [
        "api/routes/users.py",
        "web/app/dashboard/page.tsx",
        "cli/commands/deploy.py",
        "integrations/mcp-server/server.py",
        "app/compiler.py",
        "tests/test_compiler.py",
        "docs/architecture.md",
        "scripts/migrate.py",
        "config/settings.yaml",
        ".github/workflows/ci.yml",
        "app/models_v2.py",
        "app/emitters.py",
        "api/main.py",
        "web/app/page.tsx",
        "tests/test_api.py",
        "README.md",
    ]

    report = analyze_pr_safety(
        title="feat: platform-wide refactor",
        description="Refactor compiler, API, web UI, CLI, and integrations together.",
        changed_files=changed_files,
    )

    assert report.verdict == "split"
    assert report.changed_files.total == 16
    assert len(top_level_directories(changed_files)) >= 4
    assert any("split" in item.lower() for item in report.recommendations)


def test_commits_behind_threshold_recommends_rebase():
    report = analyze_pr_safety(
        title="fix: handle null session",
        description="Guard against missing session state in auth middleware.",
        changed_files=["api/routes/auth.py", "tests/test_auth.py"],
        commits_behind=12,
    )

    assert report.verdict == "rebase"
    assert report.branch_freshness.status == "stale"
    assert report.branch_freshness.commits_behind == 12
    assert any("rebase" in item.lower() for item in report.recommendations)


def test_matching_test_files_clear_test_gap():
    report = analyze_pr_safety(
        title="feat: add login flow",
        description="Add session-based login endpoints for the API.",
        changed_files=[
            "api/routes/auth.py",
            "tests/test_auth.py",
        ],
    )

    assert report.test_coverage.status == "ok"
    assert report.test_coverage.test_files == ["tests/test_auth.py"]
    assert report.test_coverage.gaps == []
    assert report.verdict == "hold"
    assert report.risky_areas.hits


def test_non_risky_source_without_tests_recommends_hold():
    report = analyze_pr_safety(
        title="refactor: tweak emitter output",
        description="Adjust formatting in the emitter module.",
        changed_files=["app/emitters.py"],
    )

    assert report.test_coverage.status == "gap"
    assert {gap.file for gap in report.test_coverage.gaps} == {"app/emitters.py"}
    assert report.risky_areas.status == "ok"
    assert report.scope_match.status == "ok"
    assert report.verdict == "hold"
    assert any("tests" in item.lower() for item in report.recommendations)


def test_colocated_tsx_test_file_clears_coverage_gap():
    report = analyze_pr_safety(
        title="fix: pr safety page copy",
        description="Adjust PR Safety page wording.",
        changed_files=[
            "web/app/pr-safety/page.tsx",
            "web/app/pr-safety/page.test.tsx",
        ],
    )

    assert report.test_coverage.status == "ok"
    assert report.test_coverage.test_files == ["web/app/pr-safety/page.test.tsx"]
    assert report.test_coverage.gaps == []
    assert report.verdict == "merge"


def test_hyphenated_test_name_clears_gap_for_underscored_module():
    report = analyze_pr_safety(
        title="refactor: user profile helper",
        description="Clean up profile helper utilities.",
        changed_files=[
            "app/user_profile.py",
            "tests/test_user-profile.py",
        ],
    )

    assert report.test_coverage.status == "ok"
    assert report.test_coverage.gaps == []
    assert report.verdict == "merge"


def test_scope_mismatch_when_description_focus_is_missing_from_files():
    report = analyze_pr_safety(
        title="fix: login redirect bug",
        description="Fix the login redirect bug in the auth middleware.",
        changed_files=["docs/CONTRIBUTING.md"],
    )

    assert report.scope_match.status == "mismatch"
    assert report.verdict == "hold"
    assert any(
        "login" in note.lower() or "auth" in note.lower() for note in report.scope_match.notes
    )


def test_unknown_branch_freshness_when_commits_behind_not_provided():
    report = analyze_pr_safety(
        title="docs: tweak changelog",
        description="Clarify release notes.",
        changed_files=["CHANGELOG.md"],
    )

    assert report.branch_freshness.status == "unknown"
    assert report.branch_freshness.commits_behind is None


def test_changed_files_are_grouped_deterministically():
    report = analyze_pr_safety(
        title="feat: auth and workflow updates",
        description="Update auth routes and CI workflow.",
        changed_files=[
            "api/routes/auth.py",
            ".github/workflows/ci.yml",
            "tests/test_auth.py",
        ],
    )

    groups = {group.name: group.files for group in report.changed_files.groups}
    assert groups["auth"] == ["api/routes/auth.py"]
    assert groups["ci"] == [".github/workflows/ci.yml"]
    assert groups["tests"] == ["tests/test_auth.py"]
