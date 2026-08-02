from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib

from setuptools import find_packages


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    pyproject_path = _repo_root() / "pyproject.toml"
    return tomllib.loads(pyproject_path.read_text(encoding="utf-8"))


def _runtime_packages() -> list[str]:
    pyproject = _load_pyproject()
    find_config = pyproject["tool"]["setuptools"]["packages"]["find"]
    return find_packages(
        where=find_config["where"][0],
        include=find_config["include"],
        exclude=find_config["exclude"],
    )


def test_runtime_package_discovery_excludes_dev_and_web_directories():
    """The published wheel should only expose real runtime packages."""
    packages = _runtime_packages()
    package_roots = {package.split(".", 1)[0] for package in packages}

    assert packages, "Runtime package discovery should not be empty"
    assert {"api", "app", "cli"}.issubset(package_roots)
    assert package_roots <= {"api", "app", "cli", "integrations"}
    assert all(
        not (package == "scripts" or package.startswith("scripts.")) for package in packages
    )
    assert all(not (package == "web" or package.startswith("web.")) for package in packages)


def test_promptc_console_script_still_points_to_cli_app():
    """The packaging fix must not break the installed promptc command."""
    pyproject = _load_pyproject()

    assert pyproject["project"]["scripts"]["promptc"] == "cli.main:app"
