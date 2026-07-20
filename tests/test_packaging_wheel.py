import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("build")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest)


def _write_decoy_package(tree: Path, relative_path: str, module_name: str) -> None:
    package_dir = tree / relative_path
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / f"{module_name}.py").write_text("VALUE = 'decoy'\n", encoding="utf-8")


def _build_fixture(tmp_path: Path, *, pyproject_text: str | None = None) -> Path:
    repo_root = _repo_root()
    fixture_root = tmp_path / "package-fixture"
    fixture_root.mkdir()

    for file_name in ("pyproject.toml", "README.md", "LICENSE", "NOTICE"):
        source = repo_root / file_name
        target = fixture_root / file_name
        if file_name == "pyproject.toml" and pyproject_text is not None:
            target.write_text(pyproject_text, encoding="utf-8")
        else:
            shutil.copy2(source, target)

    for package_dir in ("api", "app", "cli", "integrations"):
        _copy_tree(repo_root / package_dir, fixture_root / package_dir)

    # These mimic non-application top-level directories that should never ship.
    _write_decoy_package(fixture_root, "web/node_modules", "flatted")
    _write_decoy_package(fixture_root, "scripts", "debug_helper")
    _write_decoy_package(fixture_root, "extension", "plugin")
    _write_decoy_package(fixture_root, "schema", "shape")
    _write_decoy_package(fixture_root, "templates", "layout")

    return fixture_root


def _build_wheel(package_root: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(out_dir)]
    return subprocess.run(
        command,
        cwd=str(package_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_wheel_build_only_ships_application_packages(tmp_path: Path):
    fixture_root = _build_fixture(tmp_path)
    out_dir = tmp_path / "dist"
    result = _build_wheel(fixture_root, out_dir)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    wheel_path = next(out_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        unwanted = [
            name
            for name in names
            if (
                name.startswith("web/")
                or name.startswith("scripts/")
                or name.startswith("extension/")
                or name.startswith("schema/")
                or name.startswith("templates/")
                or "node_modules" in name
            )
        ]
        assert unwanted == []

        top_level_name = next(name for name in names if name.endswith("top_level.txt"))
        top_level = archive.read(top_level_name).decode("utf-8").splitlines()
        assert top_level == ["api", "app", "cli", "integrations"]

        entry_points_name = next(name for name in names if name.endswith("entry_points.txt"))
        entry_points = archive.read(entry_points_name).decode("utf-8")
        assert "promptc = cli.main:app" in entry_points


def test_removing_package_include_scope_would_ship_non_application_packages(tmp_path: Path):
    pyproject_path = _repo_root() / "pyproject.toml"
    original_pyproject = pyproject_path.read_text(encoding="utf-8")
    narrowed_include = 'include = ["api*", "app*", "cli*", "integrations*"]\n'
    assert narrowed_include in original_pyproject

    fixture_root = _build_fixture(
        tmp_path,
        pyproject_text=original_pyproject.replace(narrowed_include, "", 1),
    )
    out_dir = tmp_path / "dist"
    result = _build_wheel(fixture_root, out_dir)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    wheel_path = next(out_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        top_level_name = next(name for name in names if name.endswith("top_level.txt"))
        top_level = archive.read(top_level_name).decode("utf-8").splitlines()

        assert "web" in top_level
        assert "scripts" in top_level
        assert "extension" in top_level
        assert "schema" in top_level
        assert "templates" in top_level
        assert "web/node_modules/flatted.py" in names
