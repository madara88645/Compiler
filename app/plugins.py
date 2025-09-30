from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

try:  # Python 3.10+
    from importlib import metadata
except ImportError:  # pragma: no cover - fallback for older runtimes
    import importlib_metadata as metadata  # type: ignore

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from app.models import IR
    from app.models_v2 import IRv2


logger = logging.getLogger("promptc.plugins")

PLUGIN_FACTORY_NAMES: Sequence[str] = ("get_plugin", "register", "plugin")


@dataclass(slots=True)
class PluginContext:
    """Runtime context passed to plugins while mutating IR objects."""

    text: str
    language: str
    domain: str
    heuristics: Dict[str, Any]
    ir_metadata: Dict[str, Any]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PromptcPlugin:
    """Container describing a Prompt Compiler plugin."""

    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    process_ir: Optional[Callable[["IR", PluginContext], None]] = None
    process_ir_v2: Optional[Callable[["IRv2", PluginContext], None]] = None

    def info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "provides": [
                stage
                for stage, fn in (("ir", self.process_ir), ("ir_v2", self.process_ir_v2))
                if fn is not None
            ],
        }


_PLUGIN_CACHE: List[PromptcPlugin] | None = None


def reset_plugin_cache() -> None:
    """Reset the in-memory plugin cache (mainly for tests)."""

    global _PLUGIN_CACHE
    _PLUGIN_CACHE = None


def _instantiate_plugin(candidate: Any) -> PromptcPlugin:
    if isinstance(candidate, PromptcPlugin):
        return candidate
    if callable(candidate):
        result = candidate()
        if isinstance(result, PromptcPlugin):
            return result
    raise TypeError("Plugin factory must return PromptcPlugin instance")


def _load_from_entry_points() -> List[PromptcPlugin]:
    loaded: List[PromptcPlugin] = []
    try:
        eps = metadata.entry_points()  # type: ignore[assignment]
    except Exception as exc:  # pragma: no cover - extremely rare
        logger.debug("Failed to inspect entry points: %s", exc)
        return loaded

    if hasattr(eps, "select"):
        group = eps.select(group="promptc.plugins")  # type: ignore[attr-defined]
    else:  # pragma: no cover - legacy path
        group = eps.get("promptc.plugins", [])

    for ep in group:
        try:
            obj = ep.load()
            plugin = _instantiate_plugin(obj)
        except Exception as exc:  # pragma: no cover - logged for visibility
            logger.warning("Failed to load plugin from entry point %s: %s", ep.name, exc)
            continue
        loaded.append(plugin)
    return loaded


def _load_from_env() -> List[PromptcPlugin]:
    loaded: List[PromptcPlugin] = []
    raw = os.getenv("PROMPTC_PLUGIN_PATH")
    if not raw:
        return loaded
    for item in raw.replace(";", ",").split(","):
        target = item.strip()
        if not target:
            continue
        module_name, attr = (target.split(":", 1) + [None])[:2]
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.warning("Cannot import plugin module %s: %s", module_name, exc)
            continue
        obj: Any
        if attr:
            obj = getattr(module, attr, None)
            if obj is None:
                logger.warning(
                    "Plugin module %s missing attribute %s", module_name, attr
                )
                continue
        else:
            obj = None
            for name in PLUGIN_FACTORY_NAMES:
                if hasattr(module, name):
                    obj = getattr(module, name)
                    break
            if obj is None:
                logger.warning(
                    "Plugin module %s does not expose factory (expected one of %s)",
                    module_name,
                    ", ".join(PLUGIN_FACTORY_NAMES),
                )
                continue
        try:
            plugin = _instantiate_plugin(obj)
        except Exception as exc:
            logger.warning("Failed to instantiate plugin %s: %s", module_name, exc)
            continue
        loaded.append(plugin)
    return loaded


def get_plugins(*, refresh: bool = False) -> List[PromptcPlugin]:
    global _PLUGIN_CACHE
    if _PLUGIN_CACHE is not None and not refresh:
        return _PLUGIN_CACHE

    plugins: List[PromptcPlugin] = []
    # Order: entry points first (packaged plugins), then env overrides
    plugins.extend(_load_from_entry_points())
    plugins.extend(_load_from_env())

    # Deduplicate by (name, version) while keeping order
    seen: set[tuple[str, Optional[str]]] = set()
    unique: List[PromptcPlugin] = []
    for plugin in plugins:
        key = (plugin.name, plugin.version)
        if key in seen:
            continue
        seen.add(key)
        unique.append(plugin)

    _PLUGIN_CACHE = unique
    return unique


def describe_plugins(*, refresh: bool = False) -> List[Dict[str, Any]]:
    return [plugin.info() for plugin in get_plugins(refresh=refresh)]


def apply_plugins_ir(ir: "IR", ctx: PluginContext) -> Dict[str, Any]:
    applied: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for plugin in get_plugins():
        if plugin.process_ir is None:
            continue
        before = {c.strip().lower() for c in ir.constraints}
        try:
            plugin.process_ir(ir, ctx)
        except Exception as exc:  # pragma: no cover - safety net for plugins
            errors.append({"plugin": plugin.name, "stage": "ir", "error": repr(exc)})
            logger.warning("Plugin %s.process_ir failed: %s", plugin.name, exc)
            continue
        after = {c.strip().lower(): c for c in ir.constraints}
        added = [after[key] for key in after.keys() - before]
        applied.append(
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "stage": "ir",
                "added_constraints": added,
            }
        )
    return {"applied": applied, "errors": errors}


def apply_plugins_ir_v2(ir: "IRv2", ctx: PluginContext) -> Dict[str, Any]:
    applied: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    for plugin in get_plugins():
        if plugin.process_ir_v2 is None:
            continue
        try:
            plugin.process_ir_v2(ir, ctx)
        except Exception as exc:  # pragma: no cover
            errors.append({"plugin": plugin.name, "stage": "ir_v2", "error": repr(exc)})
            logger.warning("Plugin %s.process_ir_v2 failed: %s", plugin.name, exc)
            continue
        applied.append(
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "stage": "ir_v2",
                "added_constraints": [],
            }
        )
    return {"applied": applied, "errors": errors}


__all__ = [
    "PromptcPlugin",
    "PluginContext",
    "apply_plugins_ir",
    "apply_plugins_ir_v2",
    "describe_plugins",
    "get_plugins",
    "reset_plugin_cache",
]
