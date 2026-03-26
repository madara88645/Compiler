from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Iterable


class PathSecurityError(ValueError):
    """Raised when a user-supplied path escapes the configured allowlist."""


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEFAULT_UPLOAD_DIR = Path.home() / ".promptc_uploads"


def _chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        # Windows and some file systems ignore POSIX modes; best effort only.
        pass


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _chmod(path, 0o700)
    return path


def get_upload_dir() -> Path:
    configured = os.environ.get("PROMPTC_UPLOAD_DIR")
    target = Path(configured).expanduser() if configured else _DEFAULT_UPLOAD_DIR
    return ensure_private_dir(target.resolve())


def get_allowed_roots(extra_roots: Iterable[Path] | None = None) -> list[Path]:
    raw_roots = os.environ.get("PROMPTC_RAG_ALLOWED_ROOTS", "")
    roots: list[Path] = []

    for raw in raw_roots.split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        roots.append(Path(raw).expanduser().resolve())

    if not roots:
        roots = [Path.cwd().resolve()]

    upload_dir = get_upload_dir()
    if upload_dir not in roots:
        roots.append(upload_dir)

    for root in extra_roots or []:
        resolved = root.expanduser().resolve()
        if resolved not in roots:
            roots.append(resolved)

    return roots


def resolve_allowed_path(
    raw_path: str | Path, *, allowed_roots: Iterable[Path] | None = None
) -> Path:
    text = str(raw_path).strip()
    if not text:
        raise PathSecurityError("Path is required.")
    if "\x00" in text:
        raise PathSecurityError("Null bytes are not allowed in paths.")

    candidate = Path(text).expanduser().resolve(strict=False)
    if ".." in Path(text).parts:
        # Fail fast for explicit traversal attempts even if resolve() normalizes them.
        raise PathSecurityError("Path traversal is not allowed.")

    roots = list(allowed_roots or get_allowed_roots())
    if not roots:
        raise PathSecurityError("No allowed roots are configured.")

    for root in roots:
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue

    allowed = ", ".join(str(root) for root in roots)
    raise PathSecurityError(f"Path must stay inside an allowed root: {allowed}")


def normalize_display_name(filename: str | None) -> str:
    raw = os.path.basename((filename or "").strip())
    if raw in {"", ".", ".."}:
        return "upload.txt"
    return raw


def build_storage_name(display_name: str, content: str) -> str:
    normalized = _INVALID_FILENAME_CHARS.sub("_", display_name).strip(" .")
    path = Path(normalized or "upload.txt")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem or "upload").strip("._") or "upload"
    suffix = path.suffix[:16] if path.suffix else ".txt"
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
    return f"{stem}-{digest}{suffix}"


def store_uploaded_text(filename: str | None, content: str) -> tuple[Path, str]:
    upload_dir = get_upload_dir()
    display_name = normalize_display_name(filename)
    storage_name = build_storage_name(display_name, content)
    target = (upload_dir / storage_name).resolve()
    target.write_text(content, encoding="utf-8")
    _chmod(target, 0o600)
    return target, display_name
