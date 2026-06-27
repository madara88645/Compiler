from __future__ import annotations

from app.pr_safety.models import (
    BranchFreshnessSection,
    ChangedFilesSection,
    FileGroup,
    PrSafetyReport,
    PrSafetyVerdict,
    RiskyAreaHit,
    RiskyAreasSection,
    ScopeMatchSection,
    TestCoverageSection,
    TestGapSignal,
)
from app.pr_safety.path_rules import (
    _SCOPE_FOCUS_TERMS,
    detect_risky_areas,
    extract_scope_terms,
    group_changed_files,
    list_source_files_needing_tests,
    list_test_files,
    normalize_paths,
    path_reflects_scope_term,
    top_level_directories,
)

STALE_COMMITS_THRESHOLD = 10
SPLIT_FILE_COUNT_THRESHOLD = 15
SPLIT_TOP_LEVEL_DIRS_THRESHOLD = 4
SPLIT_MIN_FILES_FOR_DIRS = 8

_HIGH_RISK_CATEGORIES = frozenset({"auth", "secrets", "migrations", "api", "infrastructure"})


def analyze_pr_safety(
    title: str,
    description: str,
    changed_files: list[str],
    *,
    commits_behind: int | None = None,
) -> PrSafetyReport:
    files = normalize_paths(changed_files)
    grouped = group_changed_files(files)
    risky_hits = _build_risky_areas(files)
    test_section = _build_test_coverage(files)
    branch_section = _build_branch_freshness(commits_behind)
    scope_section = _build_scope_match(title, description, files)

    verdict = _pick_verdict(
        files=files,
        risky_hits=risky_hits,
        test_section=test_section,
        branch_section=branch_section,
        scope_section=scope_section,
    )
    recommendations = _build_recommendations(
        verdict=verdict,
        files=files,
        grouped=grouped,
        risky_hits=risky_hits,
        test_section=test_section,
        branch_section=branch_section,
        scope_section=scope_section,
    )

    return PrSafetyReport(
        verdict=verdict,
        title=title.strip(),
        changed_files=ChangedFilesSection(
            total=len(files),
            groups=[FileGroup(name=name, files=paths) for name, paths in sorted(grouped.items())],
        ),
        risky_areas=risky_hits,
        test_coverage=test_section,
        branch_freshness=branch_section,
        scope_match=scope_section,
        recommendations=recommendations,
    )


def _build_risky_areas(files: list[str]) -> RiskyAreasSection:
    hits = [
        RiskyAreaHit(category=category, file=file, reason=reason)
        for category, file, reason in detect_risky_areas(files)
    ]
    status = "hit" if hits else "ok"
    return RiskyAreasSection(hits=hits, status=status)


def _build_test_coverage(files: list[str]) -> TestCoverageSection:
    test_files = list_test_files(files)
    source_files = list_source_files_needing_tests(files)
    gaps: list[TestGapSignal] = []

    if not source_files:
        return TestCoverageSection(status="ok", gaps=gaps, test_files=test_files)

    for source_file in source_files:
        if _has_related_test_file(source_file, test_files):
            continue
        gaps.append(
            TestGapSignal(
                file=source_file,
                reason="Source file changed without a matching test file in this PR",
            )
        )

    status = "gap" if gaps else "ok"
    return TestCoverageSection(status=status, gaps=gaps, test_files=test_files)


def _has_related_test_file(source_file: str, test_files: list[str]) -> bool:
    if not test_files:
        return False

    stem = source_file.rsplit("/", 1)[-1]
    module = stem.rsplit(".", 1)[0]
    candidates = {
        module,
        module.replace("_", "-"),
        f"test_{module}",
        f"{module}_test",
    }

    # Bolt Optimization: Replace any() generator expression with explicit fast-path loop
    for test_file in test_files:
        test_name = test_file.rsplit("/", 1)[-1].lower()
        for candidate in candidates:
            if candidate and candidate.lower() in test_name:
                return True
        if source_file.rsplit("/", 1)[-1] in test_file:
            return True

    return False


def _build_branch_freshness(commits_behind: int | None) -> BranchFreshnessSection:
    if commits_behind is None:
        return BranchFreshnessSection(
            status="unknown",
            commits_behind=None,
            notes=["Branch freshness was not provided"],
        )

    if commits_behind < 0:
        commits_behind = 0

    if commits_behind >= STALE_COMMITS_THRESHOLD:
        return BranchFreshnessSection(
            status="stale",
            commits_behind=commits_behind,
            notes=[f"Branch is {commits_behind} commits behind the base branch"],
        )

    return BranchFreshnessSection(
        status="ok",
        commits_behind=commits_behind,
        notes=[f"Branch is {commits_behind} commits behind the base branch"],
    )


def _build_scope_match(title: str, description: str, files: list[str]) -> ScopeMatchSection:
    if not files:
        return ScopeMatchSection(status="mismatch", notes=["No changed files were provided"])

    terms = extract_scope_terms(title, description)
    focus_terms = [term for term in terms if term in _SCOPE_FOCUS_TERMS]

    # Bolt Optimization: Replace any() generator expression with fast-path loop
    missing_terms = []
    for term in focus_terms:
        found = False
        for path in files:
            if path_reflects_scope_term(path, term):
                found = True
                break
        if not found:
            missing_terms.append(term)
    notes: list[str] = []

    if missing_terms:
        notes.append(
            "PR description mentions focus areas that are not reflected in changed files: "
            + ", ".join(missing_terms)
        )

    top_levels = top_level_directories(files)
    if len(top_levels) >= SPLIT_TOP_LEVEL_DIRS_THRESHOLD and len(files) >= SPLIT_MIN_FILES_FOR_DIRS:
        narrow_scope = bool(focus_terms) and len(focus_terms) <= 2
        if narrow_scope:
            notes.append(
                "PR scope appears narrow but changes span many top-level directories: "
                + ", ".join(top_levels)
            )

    status = "mismatch" if notes else "ok"
    return ScopeMatchSection(status=status, notes=notes)


def _pick_verdict(
    *,
    files: list[str],
    risky_hits: RiskyAreasSection,
    test_section: TestCoverageSection,
    branch_section: BranchFreshnessSection,
    scope_section: ScopeMatchSection,
) -> PrSafetyVerdict:
    if branch_section.status == "stale":
        return "rebase"

    if _should_split(files):
        return "split"

    if _should_hold(risky_hits, test_section, scope_section):
        return "hold"

    return "merge"


def _should_split(files: list[str]) -> bool:
    if len(files) >= SPLIT_FILE_COUNT_THRESHOLD:
        return True

    top_levels = top_level_directories(files)
    return (
        len(top_levels) >= SPLIT_TOP_LEVEL_DIRS_THRESHOLD and len(files) >= SPLIT_MIN_FILES_FOR_DIRS
    )


def _should_hold(
    risky_hits: RiskyAreasSection,
    test_section: TestCoverageSection,
    scope_section: ScopeMatchSection,
) -> bool:
    if scope_section.status == "mismatch":
        return True
    if test_section.status == "gap":
        return True
    if not risky_hits.hits:
        return False

    categories = {hit.category for hit in risky_hits.hits}
    if categories & _HIGH_RISK_CATEGORIES:
        return True

    return len(risky_hits.hits) >= 2


def _build_recommendations(
    *,
    verdict: PrSafetyVerdict,
    files: list[str],
    grouped: dict[str, list[str]],
    risky_hits: RiskyAreasSection,
    test_section: TestCoverageSection,
    branch_section: BranchFreshnessSection,
    scope_section: ScopeMatchSection,
) -> list[str]:
    recommendations: list[str] = []

    if verdict == "rebase":
        recommendations.append("Rebase onto the latest base branch before merging")
    elif verdict == "split":
        recommendations.append("Split this PR into smaller, focused changesets")
    elif verdict == "hold":
        recommendations.append("Hold merge until the flagged safety signals are addressed")
    else:
        recommendations.append("No blocking safety signals detected; proceed with normal review")

    if branch_section.status == "stale" and verdict != "rebase":
        recommendations.append("Consider rebasing to reduce merge conflict risk")

    if scope_section.status == "mismatch":
        recommendations.extend(scope_section.notes)

    for gap in test_section.gaps[:5]:
        recommendations.append(f"Add or update tests covering `{gap.file}`")

    secret_hits = [hit for hit in risky_hits.hits if hit.category == "secrets"]
    if secret_hits:
        recommendations.append("Review environment and secret files carefully before merge")

    auth_hits = [hit for hit in risky_hits.hits if hit.category == "auth"]
    if auth_hits and test_section.status == "gap":
        recommendations.append("Auth-related changes should include explicit test coverage")

    if len(files) >= SPLIT_FILE_COUNT_THRESHOLD and verdict != "split":
        recommendations.append("Large PRs are harder to review safely; consider splitting")

    if grouped.get("docs") and len(grouped) == 1:
        recommendations.append("Docs-only change; lightweight review should be sufficient")

    return _dedupe_preserve_order(recommendations)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
