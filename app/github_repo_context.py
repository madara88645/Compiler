from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx


GITHUB_API_BASE = "https://api.github.com"
MANIFEST_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "composer.json",
    "Gemfile",
]
SCANNED_APP_DIRS = ["web", "frontend", "backend", "app", "api", "server", "client"]
MAX_HIGHLIGHTS = 6
MAX_FILES_USED = 6
MAX_STACK_ITEMS = 6
SUMMARY_MAX_CHARS = 1200


class InvalidGitHubRepoUrl(ValueError):
    pass


class GitHubRepoAnalysisError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def normalize_public_github_repo_url(repo_url: str) -> str:
    raw = (repo_url or "").strip()
    if not raw:
        raise InvalidGitHubRepoUrl("GitHub repo URL is required.")

    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise InvalidGitHubRepoUrl("Only public https://github.com/owner/repo URLs are supported.")
    if parsed.query or parsed.fragment:
        raise InvalidGitHubRepoUrl("Only root repository URLs are supported.")

    path = parsed.path.rstrip("/")
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) != 2:
        raise InvalidGitHubRepoUrl("Only root repository URLs are supported.")

    owner, repo = segments
    if repo.endswith(".git"):
        raise InvalidGitHubRepoUrl("Remove the .git suffix and use the root repository URL.")

    allowed = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not allowed.match(owner) or not allowed.match(repo):
        raise InvalidGitHubRepoUrl("Repository URL contains unsupported characters.")

    return f"https://github.com/{owner}/{repo}"


def analyze_public_github_repo(repo_url: str) -> dict[str, Any]:
    normalized_url = normalize_public_github_repo_url(repo_url)
    repo_full_name = normalized_url.replace("https://github.com/", "", 1)

    with httpx.Client(
        base_url=GITHUB_API_BASE,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "promptc-repo-context/1.0",
        },
        timeout=10.0,
        follow_redirects=True,
    ) as client:
        repo_meta = _get_json(client, f"/repos/{repo_full_name}")
        root_entries = _get_json(client, f"/repos/{repo_full_name}/contents")
        if not isinstance(root_entries, list):
            raise GitHubRepoAnalysisError("Unable to read the repository root directory.")

        default_branch = repo_meta.get("default_branch")
        readme_entry = _find_readme(root_entries)
        readme_text = _read_text_file(client, readme_entry) if readme_entry else ""
        files_used: list[str] = []
        if readme_entry:
            files_used.append(readme_entry["path"])

        manifests: dict[str, str] = {}
        for manifest_name in MANIFEST_FILES:
            entry = _find_entry(root_entries, manifest_name)
            if entry:
                content = _read_text_file(client, entry)
                if content:
                    manifests[entry["path"]] = content
                    files_used.append(entry["path"])

        top_level_dirs = [entry["name"] for entry in root_entries if entry.get("type") == "dir"]
        candidate_dirs = [name for name in top_level_dirs if name in SCANNED_APP_DIRS][:2]

        for directory in candidate_dirs:
            nested_entries = _get_json(client, f"/repos/{repo_full_name}/contents/{directory}")
            if not isinstance(nested_entries, list):
                continue
            for manifest_name in MANIFEST_FILES:
                entry = _find_entry(nested_entries, manifest_name)
                if entry and entry["path"] not in manifests:
                    content = _read_text_file(client, entry)
                    if content:
                        manifests[entry["path"]] = content
                        files_used.append(entry["path"])

        detected_stack = _detect_stack(repo_meta, manifests)
        files_used = _dedupe(files_used)[:MAX_FILES_USED]
        highlights = _build_highlights(
            repo_meta=repo_meta,
            detected_stack=detected_stack,
            top_level_dirs=top_level_dirs,
            files_used=files_used,
            manifest_paths=list(manifests.keys()),
        )[:MAX_HIGHLIGHTS]
        summary = _build_summary(
            repo_meta=repo_meta,
            detected_stack=detected_stack,
            top_level_dirs=top_level_dirs,
            files_used=files_used,
            manifest_paths=list(manifests.keys()),
            readme_text=readme_text,
        )

    return {
        "normalized_repo_url": normalized_url,
        "repo_full_name": repo_full_name,
        "default_branch": default_branch,
        "summary": summary,
        "highlights": highlights,
        "files_used": files_used,
        "detected_stack": detected_stack[:MAX_STACK_ITEMS],
    }


def _get_json(client: httpx.Client, path: str) -> Any:
    try:
        response = client.get(path)
        if response.status_code == 404:
            raise GitHubRepoAnalysisError(
                "Repository not found or not public. Only public GitHub repos are supported.",
                status_code=404,
            )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        raise GitHubRepoAnalysisError(
            "GitHub repository analysis failed.",
            status_code=404 if status_code == 404 else 502,
        ) from exc
    except httpx.HTTPError as exc:
        raise GitHubRepoAnalysisError("GitHub repository analysis failed.") from exc


def _read_text_file(client: httpx.Client, entry: dict[str, Any]) -> str:
    download_url = entry.get("download_url")
    if not download_url:
        return ""
    try:
        response = client.get(download_url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        return ""


def _find_entry(entries: list[dict[str, Any]], target_name: str) -> dict[str, Any] | None:
    target_lower = target_name.lower()
    for entry in entries:
        if entry.get("name", "").lower() == target_lower:
            return entry
    return None


def _find_readme(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in entries:
        name = entry.get("name", "").lower()
        if entry.get("type") == "file" and name.startswith("readme"):
            return entry
    return None


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _detect_stack(repo_meta: dict[str, Any], manifests: dict[str, str]) -> list[str]:
    stack: list[str] = []
    language = repo_meta.get("language")
    if isinstance(language, str) and language.strip():
        stack.append(language.strip())

    manifest_names = {path.rsplit("/", 1)[-1] for path in manifests}
    combined_manifest_text = "\n".join(manifests.values()).lower()

    if "package.json" in manifest_names:
        stack.append("Node.js")
        try:
            package_json = json.loads(
                next(text for path, text in manifests.items() if path.endswith("package.json"))
            )
            deps = {
                **(package_json.get("dependencies") or {}),
                **(package_json.get("devDependencies") or {}),
            }
            dep_names = {str(name).lower() for name in deps}
            if "next" in dep_names:
                stack.append("Next.js")
            if "react" in dep_names:
                stack.append("React")
            if "typescript" in dep_names:
                stack.append("TypeScript")
        except Exception:
            pass

    if "pyproject.toml" in manifest_names or "requirements.txt" in manifest_names:
        stack.append("Python")
    if "fastapi" in combined_manifest_text:
        stack.append("FastAPI")
    if "django" in combined_manifest_text:
        stack.append("Django")
    if "flask" in combined_manifest_text:
        stack.append("Flask")
    if "httpx" in combined_manifest_text:
        stack.append("httpx")
    if "cargo.toml" in {name.lower() for name in manifest_names}:
        stack.append("Rust")
    if "go.mod" in manifest_names:
        stack.append("Go")
    if "pom.xml" in manifest_names:
        stack.append("Java")
    if "composer.json" in manifest_names:
        stack.append("PHP")
    if "gemfile" in {name.lower() for name in manifest_names}:
        stack.append("Ruby")

    return _dedupe(stack)[:MAX_STACK_ITEMS]


def _build_highlights(
    *,
    repo_meta: dict[str, Any],
    detected_stack: list[str],
    top_level_dirs: list[str],
    files_used: list[str],
    manifest_paths: list[str],
) -> list[str]:
    repo_name = repo_meta.get("full_name") or "This repository"
    description = (repo_meta.get("description") or "").strip()
    highlights: list[str] = []
    if description:
        highlights.append(description)
    if detected_stack:
        highlights.append(f"Detected stack: {', '.join(detected_stack)}.")
    if len(top_level_dirs) >= 2:
        highlights.append(f"Top-level directories include {', '.join(top_level_dirs[:4])}.")
    if manifest_paths:
        highlights.append(f"Manifest signals found in {', '.join(manifest_paths[:3])}.")
    if files_used:
        highlights.append(f"Brief built from {', '.join(files_used[:4])}.")
    highlights.append(
        f"Use existing patterns from {repo_name}; avoid inventing missing APIs or dependencies."
    )
    return _dedupe(highlights)


def _build_summary(
    *,
    repo_meta: dict[str, Any],
    detected_stack: list[str],
    top_level_dirs: list[str],
    files_used: list[str],
    manifest_paths: list[str],
    readme_text: str,
) -> str:
    repo_name = repo_meta.get("full_name") or "This repository"
    description = (repo_meta.get("description") or "").strip()
    shape = (
        "a multi-surface repo with distinct app areas"
        if any(
            name in {"web", "frontend", "backend", "api", "client", "server"}
            for name in top_level_dirs
        )
        else "a mostly single-surface repo"
    )
    stack_phrase = (
        ", ".join(detected_stack) if detected_stack else "manifest-derived project tooling"
    )
    dir_phrase = (
        ", ".join(top_level_dirs[:5]) if top_level_dirs else "no notable top-level directories"
    )
    manifest_phrase = (
        ", ".join(manifest_paths[:4]) if manifest_paths else "no common manifests were detected"
    )
    files_phrase = ", ".join(files_used[:6]) if files_used else "repo metadata only"
    readme_signal = _extract_readme_signal(readme_text)

    parts = [
        f"{repo_name} is a public GitHub repository.",
        description
        if description
        else "No repository description was provided in GitHub metadata.",
        f"Primary stack signals point to {stack_phrase}.",
        f"The root structure suggests {shape}, with directories such as {dir_phrase}.",
        f"The shallow analysis inspected {files_phrase} and used manifest hints from {manifest_phrase}.",
        readme_signal,
        "For generator output, stay aligned with the detected stack, prefer existing project conventions, and avoid assuming internal APIs that are not visible in README or manifest-level signals.",
        "Treat this as a compact repo brief rather than a full code audit: it is suitable for tailoring an agent or skill, but not for making file-level implementation claims without further context.",
    ]
    summary = " ".join(part.strip() for part in parts if part.strip())
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[: SUMMARY_MAX_CHARS - 3].rstrip() + "..."
    return summary


def _extract_readme_signal(readme_text: str) -> str:
    text = re.sub(r"\s+", " ", (readme_text or "")).strip()
    if not text:
        return "README content was unavailable, so the brief leans more heavily on GitHub metadata and manifest files."
    compact = text[:220].strip()
    return "README signal: " + compact + ("..." if len(text) > len(compact) else "")
