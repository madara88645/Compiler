from pathlib import Path


def test_prepare_test_runtime_falls_back_when_db_dir_is_not_writable(tmp_path, monkeypatch):
    from tests.runtime_bootstrap import prepare_test_runtime

    preferred_root = tmp_path / "preferred"
    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()

    original_mkdir = Path.mkdir

    def patched_mkdir(self: Path, parents: bool = False, exist_ok: bool = False):
        if self.name == "db" and self.parent.parent.resolve() == preferred_root.resolve():
            raise PermissionError("simulated db dir failure")
        return original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", patched_mkdir)

    runtime = prepare_test_runtime(preferred_root=preferred_root, fallback_roots=[fallback_root])

    assert runtime.session_dir.parent == fallback_root.resolve()
    assert runtime.db_dir == (runtime.session_dir / "db").resolve()
    assert runtime.db_dir.is_dir()


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


def test_prepare_test_runtime_falls_back_when_session_dir_cannot_create_children(
    tmp_path, monkeypatch
):
    from tests.runtime_bootstrap import prepare_test_runtime

    preferred_root = tmp_path / "preferred"
    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()

    original_mkdir = Path.mkdir

    def patched_mkdir(self: Path, parents: bool = False, exist_ok: bool = False):
        if self.name == ".write-probe" and self.parent.parent.resolve() == preferred_root.resolve():
            raise PermissionError("simulated session dir child creation failure")
        return original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", patched_mkdir)

    runtime = prepare_test_runtime(preferred_root=preferred_root, fallback_roots=[fallback_root])

    assert runtime.session_dir.parent == fallback_root.resolve()
    assert runtime.db_dir == (runtime.session_dir / "db").resolve()
    assert runtime.db_dir.is_dir()


def test_prepare_test_runtime_avoids_mkdtemp_dirs_that_cannot_create_children(
    tmp_path, monkeypatch
):
    from tests.runtime_bootstrap import prepare_test_runtime

    preferred_root = tmp_path / "preferred"
    fallback_root = tmp_path / "fallback"

    blocked_session_dirs: set[Path] = set()

    def fake_mkdtemp(*, prefix: str, dir: str) -> str:
        root = Path(dir)
        target = root / f"{prefix}blocked-{len(blocked_session_dirs)}"
        target.mkdir(parents=True, exist_ok=True)
        blocked_session_dirs.add(target.resolve())
        return str(target)

    original_mkdir = Path.mkdir

    def patched_mkdir(self: Path, parents: bool = False, exist_ok: bool = False):
        if self.parent.resolve() in blocked_session_dirs:
            raise PermissionError("simulated child creation failure inside mkdtemp session dir")
        return original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr("tests.runtime_bootstrap.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(Path, "mkdir", patched_mkdir)

    runtime = prepare_test_runtime(preferred_root=preferred_root, fallback_roots=[fallback_root])

    assert runtime.session_dir.parent in {
        preferred_root.resolve(),
        fallback_root.resolve(),
    }
    assert runtime.session_dir.resolve() not in blocked_session_dirs
    assert runtime.db_dir == (runtime.session_dir / "db").resolve()
    assert runtime.db_dir.is_dir()


def test_prepare_test_runtime_falls_back_when_pytest_style_nested_temp_dirs_fail(
    tmp_path, monkeypatch
):
    from tests.runtime_bootstrap import prepare_test_runtime

    preferred_root = tmp_path / "preferred"
    fallback_root = tmp_path / "fallback"
    fallback_root.mkdir()

    original_mkdir = Path.mkdir

    def patched_mkdir(self: Path, parents: bool = False, exist_ok: bool = False):
        parent = self.parent.resolve()
        preferred = preferred_root.resolve()

        if self.name.startswith("pytest-of-") and parent.parent == preferred:
            raise PermissionError("simulated pytest basetemp failure")

        return original_mkdir(self, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", patched_mkdir)

    runtime = prepare_test_runtime(preferred_root=preferred_root, fallback_roots=[fallback_root])

    assert runtime.session_dir.parent == fallback_root.resolve()
    assert runtime.db_dir == (runtime.session_dir / "db").resolve()
    assert runtime.db_dir.is_dir()
