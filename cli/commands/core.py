"""Aggregator: re-exports the Typer ``app`` with all core commands registered.

Kept for import-compatibility — ``cli/main.py`` and tests do
``from cli.commands.core import app``. Command implementations live in the
sibling modules imported below (imported for their registration side-effects).
"""

from __future__ import annotations

from cli.commands._base import app, console

# Side-effect imports: each registers its commands on ``app``.
from cli.commands import compile_cmd as _compile_cmd  # noqa: F401,E402
from cli.commands import validation as _validation  # noqa: F401,E402
from cli.commands import transform as _transform  # noqa: F401,E402
from cli.commands import json_tools as _json_tools  # noqa: F401,E402
from cli.commands import pr_safety as _pr_safety  # noqa: F401,E402

__all__ = ["app", "console"]
