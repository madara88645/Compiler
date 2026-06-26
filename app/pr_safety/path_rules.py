from __future__ import annotations

import re
from fnmatch import fnmatch

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".m",
    ".mm",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
}

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}

TEST_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "*.test.ts",
    "*.test.tsx",
    "*.test.js",
    "*.test.jsx",
    "*.spec.ts",
    "*.spec.tsx",
    "*.spec.js",
    "*.spec.jsx",
    "tests/*",
    "test/*",
    "__tests__/*",
    "**/tests/*",
    "**/test/*",
    "**/__tests__/*",
)

RISKY_AREA_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "auth",
        (
            "*auth*",
            "*login*",
            "*session*",
            "*permission*",
            "*oauth*",
            "*credential*",
        ),
        "Touches authentication or authorization code",
    ),
    (
        "secrets",
        (
            ".env",
            ".env.*",
            "*secret*",
            "*credentials*",
            "*.pem",
            "*.key",
        ),
        "Touches secret or environment configuration",
    ),
    (
        "migrations",
        (
            "*/migrations/*",
            "*/alembic/*",
            "*migration*",
        ),
        "Touches database migration files",
    ),
    (
        "ci",
        (
            ".github/workflows/*",
            ".gitlab-ci.yml",
            "azure-pipelines.yml",
        ),
        "Touches CI/CD workflow configuration",
    ),
    (
        "api",
        (
            "api/routes/*",
            "*/routes/*",
            "*/endpoints/*",
            "*/controllers/*",
        ),
        "Touches API route or controller code",
    ),
    (
        "infrastructure",
        (
            "Dockerfile",
            "docker-compose*.yml",
            "docker-compose*.yaml",
            "fly.toml",
            "*.tf",
            "terraform/*",
            "infra/*",
        ),
        "Touches infrastructure or deployment configuration",
    ),
)

GROUP_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tests", TEST_FILE_PATTERNS),
    ("docs", ("docs/*", "doc/*", "*.md", "*.rst", "README*", "CHANGELOG*")),
    ("migrations", ("*/migrations/*", "*/alembic/*", "*migration*")),
    ("ci", (".github/*", ".gitlab-ci.yml", "azure-pipelines.yml")),
    ("auth", ("*auth*", "*login*", "*session*", "*permission*", "*oauth*")),
    ("secrets", (".env", ".env.*", "*secret*", "*credentials*")),
    ("config", ("*.yaml", "*.yml", "*.json", "*.toml", "*.ini", "*.cfg", "config/*")),
)

_SCOPE_FOCUS_TERMS = (
    "auth",
    "login",
    "logout",
    "signup",
    "password",
    "session",
    "oauth",
    "payment",
    "billing",
    "migration",
    "database",
    "api",
    "endpoint",
    "security",
    "permission",
    "deploy",
    "docker",
    "terraform",
    "readme",
    "docs",
    "test",
    "tests",
)

_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "into",
        "add",
        "fix",
        "update",
        "change",
        "changes",
        "feat",
        "chore",
        "refactor",
        "pull",
        "request",
        "make",
        "use",
        "using",
        "new",
        "only",
        "also",
        "will",
        "should",
        "have",
        "has",
        "been",
        "are",
        "was",
        "were",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]*[a-z0-9]|[a-z0-9]")


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def normalize_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in paths:
        path = normalize_path(raw)
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def _matches_any_pattern(path: str, patterns: tuple[str, ...]) -> bool:
    # Bolt Optimization: Replace any() generator expression with explicit loop
    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
    return False


def is_test_file(path: str) -> bool:
    normalized = normalize_path(path)
    return _matches_any_pattern(normalized, TEST_FILE_PATTERNS)


def is_doc_file(path: str) -> bool:
    normalized = normalize_path(path)
    if _matches_any_pattern(normalized, ("docs/*", "doc/*", "README*", "CHANGELOG*")):
        return True
    _, dot, ext = normalized.rpartition(".")
    return bool(dot) and f".{ext.lower()}" in DOC_EXTENSIONS


def is_config_file(path: str) -> bool:
    normalized = normalize_path(path)
    if _matches_any_pattern(
        normalized, ("config/*", "*.yaml", "*.yml", "*.json", "*.toml", "*.ini", "*.cfg")
    ):
        return True
    _, dot, ext = normalized.rpartition(".")
    return bool(dot) and f".{ext.lower()}" in CONFIG_EXTENSIONS


def is_source_file(path: str) -> bool:
    normalized = normalize_path(path)
    if is_test_file(normalized) or is_doc_file(normalized) or is_config_file(normalized):
        return False
    _, dot, ext = normalized.rpartition(".")
    return bool(dot) and f".{ext.lower()}" in SOURCE_EXTENSIONS


def group_changed_files(paths: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "source": [],
        "tests": [],
        "docs": [],
        "config": [],
        "migrations": [],
        "ci": [],
        "auth": [],
        "secrets": [],
        "other": [],
    }

    for path in normalize_paths(paths):
        assigned = False
        for group_name, patterns in GROUP_RULES:
            if _matches_any_pattern(path, patterns):
                groups[group_name].append(path)
                assigned = True
                break
        if not assigned:
            if is_source_file(path):
                groups["source"].append(path)
            elif is_doc_file(path):
                groups["docs"].append(path)
            elif is_config_file(path):
                groups["config"].append(path)
            else:
                groups["other"].append(path)

    return {name: files for name, files in groups.items() if files}


def detect_risky_areas(paths: list[str]) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for path in normalize_paths(paths):
        for category, patterns, reason in RISKY_AREA_RULES:
            if not _matches_any_pattern(path, patterns):
                continue
            key = (category, path)
            if key in seen:
                continue
            seen.add(key)
            hits.append((category, path, reason))

    return hits


def list_test_files(paths: list[str]) -> list[str]:
    return [path for path in normalize_paths(paths) if is_test_file(path)]


def list_source_files_needing_tests(paths: list[str]) -> list[str]:
    return [path for path in normalize_paths(paths) if is_source_file(path)]


def top_level_directories(paths: list[str]) -> list[str]:
    roots: set[str] = set()
    for path in normalize_paths(paths):
        parts = path.split("/")
        if len(parts) > 1:
            roots.add(parts[0])
        else:
            roots.add(path)
    return sorted(roots)


def extract_scope_terms(title: str, description: str) -> list[str]:
    text = f"{title}\n{description}".lower()
    tokens = _TOKEN_RE.findall(text)
    terms: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        cleaned = token.strip("./")
        if not cleaned or cleaned in _STOP_WORDS or len(cleaned) < 3:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        terms.append(cleaned)

    for term in _SCOPE_FOCUS_TERMS:
        if term in text and term not in seen:
            seen.add(term)
            terms.append(term)

    return terms


def path_reflects_scope_term(path: str, term: str) -> bool:
    normalized = normalize_path(path).lower()
    if term in normalized:
        return True
    stem = normalized.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0]
    return term in stem.replace("_", " ").replace("-", " ")
