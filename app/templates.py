"""Template management system for promptc.

Provides reusable prompt templates with variable substitution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


@dataclass
class TemplateVariable:
    """A variable placeholder in a template."""

    name: str
    description: str
    default: Optional[str] = None
    required: bool = True


@dataclass
class PromptTemplate:
    """A reusable prompt template with metadata."""

    id: str
    name: str
    description: str
    category: str
    template_text: str
    variables: List[TemplateVariable] = field(default_factory=list)
    example_values: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    author: Optional[str] = None
    version: str = "1.0.0"

    def render(self, variables: Dict[str, str]) -> str:
        """Render template with provided variable values."""
        text = self.template_text
        missing = []

        for var in self.variables:
            placeholder = f"{{{{{var.name}}}}}"
            value = variables.get(var.name)

            if value is None:
                if var.required and var.default is None:
                    missing.append(var.name)
                    continue
                value = var.default or ""

            text = text.replace(placeholder, value)

        if missing:
            raise ValueError(f"Missing required variables: {', '.join(missing)}")

        return text

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "template_text": self.template_text,
            "variables": [
                {
                    "name": v.name,
                    "description": v.description,
                    "default": v.default,
                    "required": v.required,
                }
                for v in self.variables
            ],
            "example_values": self.example_values,
            "tags": self.tags,
            "author": self.author,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptTemplate:
        """Create template from dictionary."""
        variables = [
            TemplateVariable(
                name=v["name"],
                description=v["description"],
                default=v.get("default"),
                required=v.get("required", True),
            )
            for v in data.get("variables", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=data["category"],
            template_text=data["template_text"],
            variables=variables,
            example_values=data.get("example_values", {}),
            tags=data.get("tags", []),
            author=data.get("author"),
            version=data.get("version", "1.0.0"),
        )


class TemplateRegistry:
    """Manages loading and accessing prompt templates."""

    def __init__(self, builtin_path: Optional[Path] = None, user_path: Optional[Path] = None):
        self.builtin_path = builtin_path or Path(__file__).parent.parent / "templates"
        self.user_path = user_path or Path.home() / ".promptc" / "templates"
        self._templates: Dict[str, PromptTemplate] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load templates on first access."""
        if self._loaded:
            return

        # Load built-in templates
        if self.builtin_path.exists():
            for file_path in self.builtin_path.glob("*.yaml"):
                try:
                    self._load_template_file(file_path)
                except Exception as e:  # pragma: no cover
                    import warnings
                    warnings.warn(f"Failed to load template {file_path}: {e}")

            for file_path in self.builtin_path.glob("*.yml"):
                try:
                    self._load_template_file(file_path)
                except Exception as e:  # pragma: no cover
                    import warnings
                    warnings.warn(f"Failed to load template {file_path}: {e}")

        # Load user templates
        if self.user_path.exists():
            for file_path in self.user_path.glob("*.yaml"):
                try:
                    self._load_template_file(file_path)
                except Exception as e:  # pragma: no cover
                    import warnings
                    warnings.warn(f"Failed to load template {file_path}: {e}")

            for file_path in self.user_path.glob("*.yml"):
                try:
                    self._load_template_file(file_path)
                except Exception as e:  # pragma: no cover
                    import warnings
                    warnings.warn(f"Failed to load template {file_path}: {e}")

        self._loaded = True

    def _load_template_file(self, path: Path) -> None:
        """Load a template from a YAML file."""
        if yaml is None:
            raise RuntimeError("PyYAML is required for template support")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return

        template = PromptTemplate.from_dict(data)
        self._templates[template.id] = template

    def list_templates(self, category: Optional[str] = None) -> List[PromptTemplate]:
        """List all available templates, optionally filtered by category."""
        self._ensure_loaded()
        templates = list(self._templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        return sorted(templates, key=lambda t: (t.category, t.name))

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        self._ensure_loaded()
        return self._templates.get(template_id)

    def get_categories(self) -> List[str]:
        """Get list of all template categories."""
        self._ensure_loaded()
        categories = {t.category for t in self._templates.values()}
        return sorted(categories)

    def save_template(self, template: PromptTemplate, user_template: bool = True) -> Path:
        """Save a template to disk."""
        if yaml is None:
            raise RuntimeError("PyYAML is required for template support")

        target_dir = self.user_path if user_template else self.builtin_path
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / f"{template.id}.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(template.to_dict(), f, sort_keys=False, allow_unicode=True)

        self._templates[template.id] = template
        return file_path

    def delete_template(self, template_id: str, user_only: bool = True) -> bool:
        """Delete a template."""
        template = self.get_template(template_id)
        if not template:
            return False

        search_dirs = [self.user_path] if user_only else [self.user_path, self.builtin_path]

        for directory in search_dirs:
            file_path = directory / f"{template_id}.yaml"
            if file_path.exists():
                file_path.unlink()
                self._templates.pop(template_id, None)
                return True

            file_path = directory / f"{template_id}.yml"
            if file_path.exists():
                file_path.unlink()
                self._templates.pop(template_id, None)
                return True

        return False


# Global registry instance
_registry: Optional[TemplateRegistry] = None


def get_registry() -> TemplateRegistry:
    """Get the global template registry."""
    global _registry
    if _registry is None:
        _registry = TemplateRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None


__all__ = [
    "PromptTemplate",
    "TemplateVariable",
    "TemplateRegistry",
    "get_registry",
    "reset_registry",
]
