from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List

CONFIG_ENV_VAR = "PROMPTC_UI_CONFIG"
DEFAULT_CONFIG_FILENAME = ".promptc_ui.json"
EXPORT_SCHEMA_VERSION = 1
MAX_CONFIG_BACKUPS = 5


@dataclass(frozen=True)
class CommandPaletteCommand:
    """Metadata for a command palette entry shared between UI and CLI."""

    id: str
    label: str


COMMAND_PALETTE_COMMANDS: List[CommandPaletteCommand] = [
    CommandPaletteCommand("generate_prompt", "🚀 Generate Prompt"),
    CommandPaletteCommand("clear_input", "🗑️ Clear Input"),
    CommandPaletteCommand("copy_system", "📋 Copy System Prompt"),
    CommandPaletteCommand("copy_user", "📋 Copy User Prompt"),
    CommandPaletteCommand("copy_expanded", "📋 Copy Expanded Prompt"),
    CommandPaletteCommand("copy_schema", "📋 Copy JSON Schema"),
    CommandPaletteCommand("analyze_quality", "🧮 Analyze Prompt Quality"),
    CommandPaletteCommand("auto_fix", "🪄 Auto-Fix Prompt"),
    CommandPaletteCommand("apply_auto_fix", "✅ Apply Auto-Fix"),
    CommandPaletteCommand("template_manager", "🧩 Template Manager"),
    CommandPaletteCommand("save_prompt", "💾 Save Prompt"),
    CommandPaletteCommand("open_prompt", "📂 Open Prompt"),
    CommandPaletteCommand("export_data", "📤 Export All Data"),
    CommandPaletteCommand("import_data", "📥 Import Data"),
    CommandPaletteCommand("show_analytics", "📊 Show Analytics"),
    CommandPaletteCommand("toggle_favorite", "⭐ Toggle Favorite"),
    CommandPaletteCommand("manage_tags", "🏷️ Manage Tags"),
    CommandPaletteCommand("manage_snippets", "📝 Manage Snippets"),
    CommandPaletteCommand("show_history", "📜 Show History"),
    CommandPaletteCommand("keyboard_shortcuts", "⌨️ Keyboard Shortcuts"),
    CommandPaletteCommand("settings", "⚙️ Settings"),
    CommandPaletteCommand("toggle_theme", "🌓 Toggle Theme"),
    CommandPaletteCommand("toggle_sidebar", "🔄 Toggle Sidebar"),
    CommandPaletteCommand("quit", "❌ Quit Application"),
]


def get_command_palette_commands() -> List[CommandPaletteCommand]:
    """Return a copy of the command palette metadata list."""

    return list(COMMAND_PALETTE_COMMANDS)


def get_command_palette_command_map() -> dict[str, CommandPaletteCommand]:
    return {cmd.id: cmd for cmd in COMMAND_PALETTE_COMMANDS}


def get_ui_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / DEFAULT_CONFIG_FILENAME


def load_ui_config() -> dict[str, Any]:  # pragma: no cover - thin IO helper
    path = get_ui_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def save_ui_config(payload: dict[str, Any]) -> None:  # pragma: no cover - thin IO helper
    path = get_ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def get_saved_palette_favorites_list(config: dict[str, Any] | None = None) -> List[str]:
    data = config if config is not None else load_ui_config()
    favorites = data.get("command_palette_favorites") or []
    if not isinstance(favorites, list):
        return []
    normalized = normalize_favorite_ids(favorites)
    return _dedupe_preserve_order(normalized)


def get_saved_palette_favorites(config: dict[str, Any] | None = None) -> set[str]:
    return set(get_saved_palette_favorites_list(config))


def persist_palette_favorites(
    favorites: Iterable[str], base_config: dict[str, Any] | None = None
) -> None:
    config = dict(base_config) if base_config is not None else load_ui_config()
    normalized = _dedupe_preserve_order(normalize_favorite_ids(favorites))
    config["command_palette_favorites"] = normalized
    save_ui_config(config)


def normalize_favorite_ids(values: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    for raw in values:
        text = str(raw).strip()
        if text:
            normalized.append(text)
    return normalized


def compute_stale_favorites(favorites: Iterable[Any], valid_ids: Iterable[str]) -> List[str]:
    """Return ordered, deduped stale favorite ids (those not in valid_ids)."""

    valid: set[str] = {str(v).strip() for v in valid_ids if str(v).strip()}
    stale: List[str] = []
    seen: set[str] = set()
    for fav in normalize_favorite_ids(favorites):
        if fav in seen:
            continue
        seen.add(fav)
        if fav not in valid:
            stale.append(fav)
    return stale


def backup_ui_config(max_backups: int = MAX_CONFIG_BACKUPS) -> Path | None:
    path = get_ui_config_path()
    if not path.exists():
        return None

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup_path)

    backups = sorted(
        path.parent.glob(f"{path.name}.*.bak"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    for stale in backups[max_backups:]:
        try:
            stale.unlink()
        except FileNotFoundError:
            continue
    return backup_path


def export_palette_favorites(path: Path, favorites: Iterable[str]) -> dict[str, Any]:
    payload = {
        "version": EXPORT_SCHEMA_VERSION,
        "favorites": normalize_favorite_ids(favorites),
        "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source_config": str(get_ui_config_path()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_exported_palette_favorites(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        raw_values = data.get("favorites", [])
    elif isinstance(data, list):
        raw_values = data
    else:
        raise ValueError("Export must be a list or a dict with a 'favorites' key.")

    if not isinstance(raw_values, list):
        raise ValueError("'favorites' must be a list of command ids.")

    return normalize_favorite_ids(raw_values)
