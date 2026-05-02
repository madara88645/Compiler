from pathlib import Path


def test_prepare_test_runtime_falls_back_when_db_dir_is_not_writable(tmp_path, monkeypatch):
    from tests.runtime_bootstrap import prepare_test_runtime

    preferred_root = tmp_path / "preferred"
    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()

    failing_session = preferred_root / "pytest-failing"
    working_session = fallback_root / "pytest-working"

    created_session_dirs: list[Path] = []

    def fake_mkdtemp(*, prefix: str, dir: str) -> str:
        target = failing_session if not created_session_dirs else working_session
        target.mkdir(parents=True, exist_ok=True)
        created_session_dirs.append(target)
        return str(target)

    original_mkdir = Path.mkdir

    def patched_mkdir(self: Path, parents: bool = False, exist_ok: bool = False):
        if self == failing_session / "db":
            raise PermissionError("simulated db dir failure")
        return original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr("tests.runtime_bootstrap.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(Path, "mkdir", patched_mkdir)

    runtime = prepare_test_runtime(preferred_root=preferred_root, fallback_roots=[fallback_root])

    assert runtime.session_dir == working_session.resolve()
    assert runtime.db_dir == (working_session / "db").resolve()
    assert runtime.db_dir.is_dir()
    assert created_session_dirs == [failing_session, working_session]


def test_prepare_test_runtime_sets_process_temp_environment(tmp_path):
    from tests.runtime_bootstrap import prepare_test_runtime

    runtime = prepare_test_runtime(
        preferred_root=tmp_path / "preferred", fallback_roots=[tmp_path / "fallback"]
    )

    assert runtime.session_dir.is_dir()
    assert runtime.db_dir.is_dir()
    assert runtime.env_updates["TMP"] == str(runtime.session_dir)
    assert runtime.env_updates["TEMP"] == str(runtime.session_dir)
    assert runtime.env_updates["TMPDIR"] == str(runtime.session_dir)
    assert runtime.env_updates["DB_DIR"] == str(runtime.db_dir)
