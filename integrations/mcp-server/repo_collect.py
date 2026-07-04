from __future__ import annotations

import os

# Small allowlist of non-secret manifest/config files worth sending to the backend.
_MANIFEST_FILES = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "Gemfile",
    "Makefile",
    "makefile",
    "tox.ini",
    "setup.cfg",
)
_MAX_BYTES = 64_000  # never read large files


def _read(path: str) -> str | None:
    try:
        if os.path.getsize(path) > _MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def collect_repo_facts(repo_path: str) -> dict:
    """Read a small allowlist of manifest files + a shallow tree from a local repo.

    Never reads secrets (.env and friends are not in the allowlist). Returns a plain dict
    matching the backend `RepoFacts` model.
    """
    files: dict[str, str] = {}
    # top-level manifests
    for rel in _MANIFEST_FILES:
        content = _read(os.path.join(repo_path, rel))
        if content is not None:
            files[rel] = content
    # one level down (e.g. web/package.json)
    try:
        for entry in sorted(os.listdir(repo_path)):
            sub = os.path.join(repo_path, entry)
            if os.path.isdir(sub) and not entry.startswith("."):
                for rel in _MANIFEST_FILES:
                    content = _read(os.path.join(sub, rel))
                    if content is not None:
                        files[f"{entry}/{rel}"] = content
    except OSError:
        pass

    claude_md = os.path.join(repo_path, "CLAUDE.md")
    if os.path.isfile(claude_md):
        content = _read(claude_md)
        if content is not None:
            files["CLAUDE.md"] = content

    try:
        tree = sorted(os.listdir(repo_path))
    except OSError:
        tree = []

    return {
        "files": files,
        "tree": tree,
        "has_claude_md": os.path.isfile(claude_md),
        "has_claude_dir": os.path.isdir(os.path.join(repo_path, ".claude")),
    }
