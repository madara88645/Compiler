import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TestRuntime:
    session_dir: Path
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


def prepare_test_runtime(
    *,
    preferred_root: Path,
    fallback_roots: Iterable[Path] = (),
) -> TestRuntime:
    errors: list[str] = []

    for root in _candidate_roots(preferred_root, fallback_roots):
        try:
            root.mkdir(parents=True, exist_ok=True)
            session_dir = Path(tempfile.mkdtemp(prefix="pytest-", dir=str(root))).resolve()
            db_dir = (session_dir / "db").resolve()
            db_dir.mkdir(parents=True, exist_ok=True)

            env_updates = {
                "TMP": str(session_dir),
                "TEMP": str(session_dir),
                "TMPDIR": str(session_dir),
                "DB_DIR": str(db_dir),
            }
            return TestRuntime(session_dir=session_dir, db_dir=db_dir, env_updates=env_updates)
        except PermissionError as exc:
            errors.append(f"{root}: {exc}")

    joined_errors = "; ".join(errors) if errors else "no candidate roots were provided"
    raise PermissionError(
        f"Unable to initialize pytest runtime directories. Tried: {joined_errors}"
    )


def apply_test_runtime(runtime: TestRuntime) -> None:
    for env_name, value in runtime.env_updates.items():
        os.environ[env_name] = value
    tempfile.tempdir = str(runtime.session_dir)
