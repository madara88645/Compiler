from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List

CONFIG_ENV_VAR = "PROMPTC_UI_CONFIG"
DEFAULT_CONFIG_FILENAME = ".promptc_ui.json"


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


def get_saved_palette_favorites(config: dict[str, Any] | None = None) -> set[str]:
    data = config if config is not None else load_ui_config()
    favorites = data.get("command_palette_favorites") or []
    return {str(item) for item in favorites if item}


def persist_palette_favorites(
    favorites: Iterable[str], base_config: dict[str, Any] | None = None
) -> None:
    config = dict(base_config) if base_config is not None else load_ui_config()
    normalized = sorted({str(item) for item in favorites if item})
    config["command_palette_favorites"] = normalized
    save_ui_config(config)
