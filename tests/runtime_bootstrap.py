import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import uuid4


@dataclass(frozen=True)
class TestRuntime:
    session_dir: Path
    temp_root: Path
    db_dir: Path
    env_updates: dict[str, str]


def _candidate_roots(preferred_root: Path, fallback_roots: Iterable[Path]) -> list[Path]:
    roots = [preferred_root, *fallback_roots]
    unique_roots: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_roots.append(resolved)

    return unique_roots


def _create_session_dir(root: Path) -> Path:
    session_dir = (root / f"pytest-{uuid4().hex[:8]}").resolve()
    session_dir.mkdir(parents=False, exist_ok=False)
    probe_dir = session_dir / ".write-probe"
    pytest_probe_root = session_dir / "pytest-of-probe"
    pytest_probe_leaf = pytest_probe_root / "pytest-0"

    try:
        probe_dir.mkdir(parents=True, exist_ok=False)
        pytest_probe_root.mkdir(parents=True, exist_ok=False)
        pytest_probe_leaf.mkdir(parents=False, exist_ok=False)
        os.scandir(pytest_probe_root).close()
        os.scandir(pytest_probe_leaf).close()
    finally:
        if probe_dir.exists():
            probe_dir.rmdir()
        if pytest_probe_leaf.exists():
            pytest_probe_leaf.rmdir()
        if pytest_probe_root.exists():
            pytest_probe_root.rmdir()

    return session_dir


def prepare_test_runtime(
    *,
    preferred_root: Path,
    fallback_roots: Iterable[Path] = (),
) -> TestRuntime:
    errors: list[str] = []

    for root in _candidate_roots(preferred_root, fallback_roots):
        try:
            root.mkdir(parents=True, exist_ok=True)
            session_dir = _create_session_dir(root)
            temp_root = (session_dir / "tmp").resolve()
            temp_root.mkdir(parents=True, exist_ok=True)
            db_dir = (session_dir / "db").resolve()
            db_dir.mkdir(parents=True, exist_ok=True)

            env_updates = {
                "TMP": str(temp_root),
                "TEMP": str(temp_root),
                "TMPDIR": str(temp_root),
                "DB_DIR": str(db_dir),
            }
            return TestRuntime(
                session_dir=session_dir,
                temp_root=temp_root,
                db_dir=db_dir,
                env_updates=env_updates,
            )
        except PermissionError as exc:
            if "session_dir" in locals():
                shutil.rmtree(session_dir, ignore_errors=True)
            errors.append(f"{root}: {exc}")

    joined_errors = "; ".join(errors) if errors else "no candidate roots were provided"
    raise PermissionError(
        f"Unable to initialize pytest runtime directories. Tried: {joined_errors}"
    )


def apply_test_runtime(runtime: TestRuntime) -> None:
    for env_name, value in runtime.env_updates.items():
        os.environ[env_name] = value
    tempfile.tempdir = str(runtime.temp_root)
