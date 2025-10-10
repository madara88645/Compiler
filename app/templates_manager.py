"""Enhanced template management system with user-friendly operations.

Provides high-level template management operations with validation,
interactive prompts, and rich CLI output support.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.templates import PromptTemplate, TemplateRegistry, TemplateVariable, get_registry


@dataclass
class TemplateUsageStats:
    """Statistics about template usage."""

    template_id: str
    use_count: int
    last_used: str
    average_rating: float = 0.0


class TemplatesManager:
    """High-level template management with usage tracking and validation."""

    def __init__(self, registry: Optional[TemplateRegistry] = None):
        self.registry = registry or get_registry()
        self.stats_file = Path.home() / ".promptc" / "template_stats.json"
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        self._stats: Dict[str, TemplateUsageStats] = {}
        self._load_stats()

    def _load_stats(self) -> None:
        """Load usage statistics from disk."""
        if not self.stats_file.exists():
            return

        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._stats = {
                    tid: TemplateUsageStats(**stats) for tid, stats in data.items()
                }
        except Exception:
            self._stats = {}

    def _save_stats(self) -> None:
        """Save usage statistics to disk."""
        data = {
            tid: {
                "template_id": stats.template_id,
                "use_count": stats.use_count,
                "last_used": stats.last_used,
                "average_rating": stats.average_rating,
            }
            for tid, stats in self._stats.items()
        }

        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def list_templates(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[PromptTemplate]:
        """
        List templates with optional filtering.

        Args:
            category: Filter by category
            tag: Filter by tag
            search: Search in name, description, or template text

        Returns:
            List of matching templates
        """
        templates = self.registry.list_templates(category=category)

        if tag:
            templates = [t for t in templates if tag in t.tags]

        if search:
            search_lower = search.lower()
            templates = [
                t
                for t in templates
                if search_lower in t.name.lower()
                or search_lower in t.description.lower()
                or search_lower in t.template_text.lower()
            ]

        return templates

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        return self.registry.get_template(template_id)

    def create_template(
        self,
        template_id: str,
        name: str,
        description: str,
        category: str,
        template_text: str,
        variables: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
    ) -> PromptTemplate:
        """
        Create a new custom template.

        Args:
            template_id: Unique identifier
            name: Display name
            description: Template description
            category: Template category
            template_text: Template content with {{variable}} placeholders
            variables: List of variable definitions
            tags: Optional tags
            author: Optional author name

        Returns:
            Created template

        Raises:
            ValueError: If template_id already exists
        """
        if self.registry.get_template(template_id):
            raise ValueError(f"Template with id '{template_id}' already exists")

        # Convert variable dicts to TemplateVariable objects
        var_objects = []
        if variables:
            for var in variables:
                var_objects.append(
                    TemplateVariable(
                        name=var["name"],
                        description=var["description"],
                        default=var.get("default"),
                        required=var.get("required", True),
                    )
                )

        template = PromptTemplate(
            id=template_id,
            name=name,
            description=description,
            category=category,
            template_text=template_text,
            variables=var_objects,
            tags=tags or [],
            author=author,
            version="1.0.0",
        )

        # Save to user templates directory
        self.registry.save_template(template, user_template=True)

        return template

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        template_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[PromptTemplate]:
        """
        Update an existing template.

        Args:
            template_id: Template to update
            name: New name (optional)
            description: New description (optional)
            template_text: New template text (optional)
            tags: New tags (optional)

        Returns:
            Updated template or None if not found
        """
        template = self.registry.get_template(template_id)
        if not template:
            return None

        # Create updated template
        updated = PromptTemplate(
            id=template.id,
            name=name or template.name,
            description=description or template.description,
            category=template.category,
            template_text=template_text or template.template_text,
            variables=template.variables,
            tags=tags if tags is not None else template.tags,
            author=template.author,
            version=template.version,
        )

        # Save updated template
        self.registry.save_template(updated, user_template=True)

        return updated

    def delete_template(self, template_id: str, user_only: bool = True) -> bool:
        """
        Delete a template.

        Args:
            template_id: Template to delete
            user_only: Only delete user templates (not built-in)

        Returns:
            True if deleted successfully
        """
        return self.registry.delete_template(template_id, user_only=user_only)

    def use_template(
        self, template_id: str, variables: Dict[str, str]
    ) -> Optional[str]:
        """
        Use a template by rendering it with provided variables.

        Args:
            template_id: Template to use
            variables: Variable values

        Returns:
            Rendered template text or None if template not found

        Raises:
            ValueError: If required variables are missing
        """
        template = self.registry.get_template(template_id)
        if not template:
            return None

        # Render template
        rendered = template.render(variables)

        # Update usage stats
        if template_id not in self._stats:
            self._stats[template_id] = TemplateUsageStats(
                template_id=template_id,
                use_count=0,
                last_used=datetime.now().isoformat(),
            )

        stats = self._stats[template_id]
        stats.use_count += 1
        stats.last_used = datetime.now().isoformat()
        self._save_stats()

        return rendered

    def get_categories(self) -> List[str]:
        """Get all template categories."""
        return self.registry.get_categories()

    def get_stats(self, template_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            template_id: Get stats for specific template (None = all stats)

        Returns:
            Statistics dictionary
        """
        if template_id:
            stats = self._stats.get(template_id)
            if not stats:
                return {
                    "template_id": template_id,
                    "use_count": 0,
                    "last_used": None,
                }
            return {
                "template_id": stats.template_id,
                "use_count": stats.use_count,
                "last_used": stats.last_used,
                "average_rating": stats.average_rating,
            }

        # Return overall stats
        total_uses = sum(s.use_count for s in self._stats.values())
        templates_used = len(self._stats)

        most_used = []
        if self._stats:
            sorted_stats = sorted(
                self._stats.values(), key=lambda s: s.use_count, reverse=True
            )
            most_used = [
                {
                    "template_id": s.template_id,
                    "use_count": s.use_count,
                    "last_used": s.last_used,
                }
                for s in sorted_stats[:5]
            ]

        return {
            "total_templates": len(self.registry.list_templates()),
            "templates_used": templates_used,
            "total_uses": total_uses,
            "most_used": most_used,
        }

    def export_template(self, template_id: str, output_path: Path) -> bool:
        """
        Export a template to a YAML file.

        Args:
            template_id: Template to export
            output_path: Output file path

        Returns:
            True if exported successfully
        """
        template = self.registry.get_template(template_id)
        if not template:
            return False

        try:
            import yaml

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    template.to_dict(), f, sort_keys=False, allow_unicode=True
                )
            return True
        except Exception:
            return False

    def import_template(self, input_path: Path) -> Optional[PromptTemplate]:
        """
        Import a template from a YAML file.

        Args:
            input_path: Input file path

        Returns:
            Imported template or None if failed
        """
        try:
            import yaml

            with open(input_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            template = PromptTemplate.from_dict(data)

            # Save to user templates
            self.registry.save_template(template, user_template=True)

            return template
        except Exception:
            return None

    def validate_template(self, template_id: str) -> Dict[str, Any]:
        """
        Validate a template and return validation results.

        Args:
            template_id: Template to validate

        Returns:
            Validation results with issues list
        """
        template = self.registry.get_template(template_id)
        if not template:
            return {"valid": False, "error": "Template not found"}

        issues = []

        # Check for undefined variables in template text
        import re

        placeholders = set(re.findall(r"\{\{(\w+)\}\}", template.template_text))
        defined_vars = {v.name for v in template.variables}

        undefined = placeholders - defined_vars
        if undefined:
            issues.append(f"Undefined variables in template: {', '.join(undefined)}")

        unused = defined_vars - placeholders
        if unused:
            issues.append(f"Unused variable definitions: {', '.join(unused)}")

        # Check for required variables without defaults
        required_no_default = [
            v.name for v in template.variables if v.required and v.default is None
        ]

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "placeholders": sorted(placeholders),
            "defined_variables": sorted(defined_vars),
            "required_variables": required_no_default,
        }


# Global manager instance
_manager: Optional[TemplatesManager] = None


def get_templates_manager() -> TemplatesManager:
    """Get the global templates manager instance."""
    global _manager
    if _manager is None:
        _manager = TemplatesManager()
    return _manager


__all__ = ["TemplatesManager", "TemplateUsageStats", "get_templates_manager"]
