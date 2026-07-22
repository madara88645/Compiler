from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_minimal_repo(root: Path) -> None:
    repo_root = _repo_root()
    pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    _write(root, "pyproject.toml", pyproject_text)
    _write(root, "README.md", "# packaging fixture\n")

    for package in (
        "api",
        "app",
        "cli",
        "integrations",
        "scripts",
        "web",
        "web/node_modules",
        "extension",
        "schema",
        "templates",
    ):
        _write(root, f"{package}/__init__.py", "")

    _write(root, "cli/main.py", "app = object()\n")
    _write(root, "app/_schemas/example.json", "{}\n")
    _write(root, "app/_builtin_templates/example.yaml", "name: fixture\n")
    _write(root, "web/node_modules/flatted.py", "VALUE = 'should not ship'\n")


def test_wheel_build_only_ships_application_packages(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    _seed_minimal_repo(fixture_root)

    pyproject = tomllib.loads((fixture_root / "pyproject.toml").read_text(encoding="utf-8"))
    dist_dir = tmp_path / "dist"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(dist_dir),
        ],
        cwd=fixture_root,
        check=True,
        capture_output=True,
        text=True,
    )

    wheel_path = next(dist_dir.glob("*.whl"))
    expected_prefix = (
        f"{pyproject['project']['name'].replace('-', '_')}-{pyproject['project']['version']}-"
    )
    assert wheel_path.name.startswith(expected_prefix)

    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        package_roots = {
            name.split("/", 1)[0]
            for name in names
            if "/" in name and ".dist-info/" not in name
        }
        assert package_roots == {"api", "app", "cli", "integrations"}
        assert not any(
            name.startswith(("scripts/", "web/", "extension/", "schema/", "templates/"))
            for name in names
        )

        dist_info_dir = next(name.split("/", 1)[0] for name in names if ".dist-info/" in name)
        entry_points = archive.read(f"{dist_info_dir}/entry_points.txt").decode("utf-8")
        assert "[console_scripts]" in entry_points
        assert "promptc = cli.main:app" in entry_points
