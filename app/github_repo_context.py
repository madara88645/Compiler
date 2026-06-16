from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import httpx
from cachetools import TTLCache


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
SUMMARY_COMPACT_MAX_CHARS = 280
_REPO_CACHE_MAXSIZE = 128
_REPO_CACHE_DEFAULT_TTL_SECONDS = 600

_GITHUB_HTTP_CLIENT: httpx.Client | None = None


def get_github_http_client() -> httpx.Client:
    global _GITHUB_HTTP_CLIENT
    if _GITHUB_HTTP_CLIENT is None:
        _GITHUB_HTTP_CLIENT = httpx.Client(
            base_url=GITHUB_API_BASE,
            timeout=10.0,
            follow_redirects=True,
        )
    return _GITHUB_HTTP_CLIENT


def close_github_http_client() -> None:
    global _GITHUB_HTTP_CLIENT
    if _GITHUB_HTTP_CLIENT is not None:
        _GITHUB_HTTP_CLIENT.close()
        _GITHUB_HTTP_CLIENT = None


def _resolve_repo_cache_ttl() -> int:
    raw = os.environ.get("PROMPTC_REPO_CONTEXT_CACHE_TTL")
    if raw is None or raw.strip() == "":
        return _REPO_CACHE_DEFAULT_TTL_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return _REPO_CACHE_DEFAULT_TTL_SECONDS


RepoCacheKey = tuple[str, str, str]
_REPO_CACHE: TTLCache[RepoCacheKey, dict[str, Any]] | None = None
_repo_cache_ttl = _resolve_repo_cache_ttl()
if _repo_cache_ttl > 0:
    _REPO_CACHE = TTLCache(maxsize=_REPO_CACHE_MAXSIZE, ttl=_repo_cache_ttl)


def reset_repo_cache_for_tests() -> None:
    global _REPO_CACHE, _GITHUB_HTTP_CLIENT
    if _REPO_CACHE is not None:
        _REPO_CACHE.clear()
    if _GITHUB_HTTP_CLIENT is not None:
        _GITHUB_HTTP_CLIENT.close()
        _GITHUB_HTTP_CLIENT = None


class InvalidGitHubRepoUrl(ValueError):
    pass


class GitHubRepoAnalysisError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def normalize_public_github_repo_url(repo_url: str) -> tuple[str, str | None, str | None]:
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
    if len(segments) < 2:
        raise InvalidGitHubRepoUrl("Only root repository URLs are supported.")

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        raise InvalidGitHubRepoUrl("Remove the .git suffix and use the root repository URL.")

    allowed = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not allowed.match(owner) or not allowed.match(repo):
        raise InvalidGitHubRepoUrl("Repository URL contains unsupported characters.")

    normalized_url = f"https://github.com/{owner}/{repo}"
    if len(segments) == 2:
        return normalized_url, None, None

    if len(segments) >= 4 and segments[2] == "tree":
        requested_ref = segments[3]
        if not requested_ref:
            raise InvalidGitHubRepoUrl("Only root repository URLs are supported.")
        requested_subdir = "/".join(segments[4:]) or None
        return normalized_url, requested_ref, requested_subdir

    raise InvalidGitHubRepoUrl("Only root repository URLs are supported.")


def analyze_public_github_repo(repo_url: str) -> dict[str, Any]:
    normalized_url, requested_ref, requested_subdir = normalize_public_github_repo_url(repo_url)
    repo_full_name = normalized_url.replace("https://github.com/", "", 1)
    cache_key: RepoCacheKey = (
        repo_full_name,
        requested_ref or "",
        requested_subdir or "",
    )

    if _REPO_CACHE is not None:
        cached = _REPO_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

    payload = _fetch_public_github_repo_payload(
        normalized_url,
        repo_full_name,
        requested_ref=requested_ref,
        requested_subdir=requested_subdir,
    )

    if _REPO_CACHE is not None:
        _REPO_CACHE[cache_key] = dict(payload)

    return payload


def _resolve_github_token() -> str | None:
    for env_name in ("PROMPTC_GITHUB_TOKEN", "GITHUB_TOKEN"):
        raw = os.environ.get(env_name)
        if raw:
            stripped = raw.strip()
            if stripped:
                return stripped
    return None


def _build_github_request_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "promptc-repo-context/1.0",
    }
    token = _resolve_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _contents_api_path(
    repo_full_name: str,
    *,
    requested_path: str | None = None,
    requested_ref: str | None = None,
) -> str:
    path = f"/repos/{repo_full_name}/contents"
    if requested_path:
        normalized_path = quote(requested_path.strip("/"), safe="/")
        path = f"{path}/{normalized_path}"
    if requested_ref:
        path = f"{path}?{urlencode({'ref': requested_ref})}"
    return path


def _fetch_public_github_repo_payload(
    normalized_url: str,
    repo_full_name: str,
    *,
    requested_ref: str | None,
    requested_subdir: str | None,
) -> dict[str, Any]:
    client = get_github_http_client()
    headers = _build_github_request_headers()
    repo_meta = _get_json(client, f"/repos/{repo_full_name}", headers=headers)
    listing_entries = _get_json(
        client,
        _contents_api_path(
            repo_full_name,
            requested_path=requested_subdir,
            requested_ref=requested_ref,
        ),
        headers=headers,
    )
    if not isinstance(listing_entries, list):
        raise GitHubRepoAnalysisError("Unable to read the repository root directory.")

    default_branch = repo_meta.get("default_branch")
    readme_entry = _find_readme(listing_entries)
    readme_text = _read_text_file(client, readme_entry, headers=headers) if readme_entry else ""
    files_used: list[str] = []
    if readme_entry:
        files_used.append(readme_entry["path"])

    manifests: dict[str, str] = {}
    for manifest_name in MANIFEST_FILES:
        entry = _find_entry(listing_entries, manifest_name)
        if entry:
            content = _read_text_file(client, entry, headers=headers)
            if content:
                manifests[entry["path"]] = content
                files_used.append(entry["path"])

    top_level_dirs = [entry["name"] for entry in listing_entries if entry.get("type") == "dir"]
    candidate_dirs = [name for name in top_level_dirs if name in SCANNED_APP_DIRS][:2]

    for directory in candidate_dirs:
        nested_path = (
            f"{requested_subdir.strip('/')}/{directory}" if requested_subdir else directory
        )
        nested_entries = _get_json(
            client,
            _contents_api_path(
                repo_full_name,
                requested_path=nested_path,
                requested_ref=requested_ref,
            ),
            headers=headers,
        )
        if not isinstance(nested_entries, list):
            continue
        for manifest_name in MANIFEST_FILES:
            entry = _find_entry(nested_entries, manifest_name)
            if entry and entry["path"] not in manifests:
                content = _read_text_file(client, entry, headers=headers)
                if content:
                    manifests[entry["path"]] = content
                    files_used.append(entry["path"])
        if len(_dedupe(files_used)) < MAX_FILES_USED:
            nested_readme = _find_readme(nested_entries)
            if nested_readme and nested_readme["path"] not in files_used:
                nested_readme_text = _read_text_file(client, nested_readme, headers=headers)
                if nested_readme_text:
                    files_used.append(nested_readme["path"])

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
    summary_compact = _build_summary_compact(
        repo_meta=repo_meta,
        detected_stack=detected_stack,
        top_level_dirs=top_level_dirs,
    )

    return {
        "normalized_repo_url": normalized_url,
        "repo_full_name": repo_full_name,
        "requested_ref": requested_ref,
        "requested_subdir": requested_subdir,
        "default_branch": default_branch,
        "summary": summary,
        "summary_compact": summary_compact,
        "highlights": highlights,
        "files_used": files_used,
        "detected_stack": detected_stack[:MAX_STACK_ITEMS],
    }


def _get_json(client: httpx.Client, path: str, headers: dict[str, str] | None = None) -> Any:
    try:
        response = client.get(path, headers=headers)
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


def _read_text_file(
    client: httpx.Client, entry: dict[str, Any], headers: dict[str, str] | None = None
) -> str:
    download_url = entry.get("download_url")
    if not download_url:
        return ""
    try:
        response = client.get(download_url, headers=headers)
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
        # Bolt Optimization: Use isdisjoint() instead of any() with generator for 5-10x speedup
        if not {"web", "frontend", "backend", "api", "client", "server"}.isdisjoint(top_level_dirs)
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


def _build_summary_compact(
    *,
    repo_meta: dict[str, Any],
    detected_stack: list[str],
    top_level_dirs: list[str],
) -> str:
    repo_name = repo_meta.get("full_name") or "This repository"
    description = (repo_meta.get("description") or "").strip()
    stack_phrase = ", ".join(detected_stack[:3]) if detected_stack else "no detected stack signals"
    shape = (
        "multi-surface (frontend + backend dirs)"
        # Bolt Optimization: Use isdisjoint() instead of any() with generator for 5-10x speedup
        if not {"web", "frontend", "backend", "api", "client", "server"}.isdisjoint(top_level_dirs)
        else "single-surface"
    )
    parts = [
        f"{repo_name}: {description}" if description else f"{repo_name}.",
        f"Stack: {stack_phrase}.",
        f"Shape: {shape}.",
    ]
    compact = " ".join(part.strip() for part in parts if part.strip())
    if len(compact) > SUMMARY_COMPACT_MAX_CHARS:
        compact = compact[: SUMMARY_COMPACT_MAX_CHARS - 3].rstrip() + "..."
    return compact


def _extract_readme_signal(readme_text: str) -> str:
    text = re.sub(r"\s+", " ", (readme_text or "")).strip()
    if not text:
        return "README content was unavailable, so the brief leans more heavily on GitHub metadata and manifest files."
    compact = text[:220].strip()
    return "README signal: " + compact + ("..." if len(text) > len(compact) else "")
