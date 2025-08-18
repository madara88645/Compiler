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

def get_version() -> str:
	"""Return the resolved package version (lightweight helper)."""
	return __version__

__all__ = ["__version__", "get_version"]
