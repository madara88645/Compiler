from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ContextPreset:
    name: str
    content: str


@dataclass
class ContextPresetStore:
    path: Optional[Path] = None
    presets: List[ContextPreset] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = Path.home() / ".promptc_context_presets.json"
        self.path = Path(self.path)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                data = []
        except Exception:
            data = []
        self.presets = []
        for entry in data:
            if isinstance(entry, dict):
                name = str(entry.get("name", ""))
                content = str(entry.get("content", ""))
                if name:
                    self.presets.append(ContextPreset(name=name, content=content))

    def save(self) -> None:
        try:
            payload = [preset.__dict__ for preset in self.presets]
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def upsert(self, name: str, content: str) -> None:
        name = name.strip()
        if not name:
            return
        for preset in self.presets:
            if preset.name.lower() == name.lower():
                preset.name = name
                preset.content = content
                self.save()
                return
        self.presets.append(ContextPreset(name=name, content=content))
        self.save()

    def delete(self, name: str) -> bool:
        for idx, preset in enumerate(self.presets):
            if preset.name == name:
                del self.presets[idx]
                self.save()
                return True
        return False

    def rename(self, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name:
            return False
        for preset in self.presets:
            if preset.name == old_name:
                preset.name = new_name
                self.save()
                return True
        return False

    def get(self, name: str) -> Optional[ContextPreset]:
        for preset in self.presets:
            if preset.name == name:
                return preset
        return None

    def list_names(self) -> List[str]:
        return [preset.name for preset in self.presets]
