"""Core package initializer.

Exposes a best-effort __version__ attribute so both the API and CLI can
surface the current package version without failing in editable/dev mode.
Falls back to a dev tag if distribution metadata is not present.
"""

from __future__ import annotations

try:  # Prefer installed distribution metadata
	from importlib.metadata import version, PackageNotFoundError  # type: ignore

	try:
		__version__ = version("promptc")  # Distribution name as defined in pyproject
	except PackageNotFoundError:
		__version__ = "0.0.0-dev"
except Exception:  # pragma: no cover - extremely defensive
	__version__ = "0.0.0-dev"

# Public constants for IR and package versions (used by API/CLI/emitters)
IR_SCHEMA_VERSION = "2.0"


def get_version() -> str:
	"""Return the resolved package version (lightweight helper)."""
	return __version__

def _read_git_sha() -> str | None:  # pragma: no cover - env dependent
	try:
		import subprocess
		sha = (
			subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
			.decode("utf-8")
			.strip()
		)
		return sha or None
	except Exception:
		return None

def get_build_info() -> dict:
	"""Return build info: package version, git SHA (if available), and IR schema version."""
	return {
		"version": get_version(),
		"git_sha": _read_git_sha(),
		"ir_schema_version": IR_SCHEMA_VERSION,
	}

__all__ = ["__version__", "get_version", "get_build_info", "IR_SCHEMA_VERSION"]
