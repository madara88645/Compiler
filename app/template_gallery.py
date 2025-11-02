"""Template Gallery - Categorized prompt templates with preview and search.

Provides a curated collection of high-quality prompt templates organized by
category, with search, preview, and quick-use functionality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class GalleryTemplate:
    """A template in the gallery."""

    id: str
    name: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    difficulty: str = "intermediate"  # beginner, intermediate, advanced
    author: str = "PromptC Team"
    version: str = "1.0"
    template: Dict[str, Any] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)

    def matches_search(self, query: str) -> bool:
        """Check if template matches search query."""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower()
            or query_lower in self.description.lower()
            or query_lower in self.category.lower()
            or any(query_lower in tag.lower() for tag in self.tags)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "author": self.author,
            "version": self.version,
            "template": self.template,
            "examples": self.examples,
            "use_cases": self.use_cases,
        }


class TemplateGallery:
    """Manages the template gallery."""

    def __init__(self, gallery_dir: Optional[Path] = None):
        """Initialize gallery.

        Args:
            gallery_dir: Directory containing gallery templates
        """
        if gallery_dir is None:
            gallery_dir = Path.home() / ".promptc" / "gallery"

        self.gallery_dir = gallery_dir
        self.gallery_dir.mkdir(parents=True, exist_ok=True)
        self.templates: Dict[str, GalleryTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all templates from gallery directory."""
        self.templates.clear()

        # Load built-in templates
        self._load_builtin_templates()

        # Load custom templates from gallery directory
        for template_file in self.gallery_dir.glob("*.yaml"):
            try:
                template = self._load_template_file(template_file)
                if template:
                    self.templates[template.id] = template
            except Exception:
                # Skip invalid templates
                pass

    def _load_builtin_templates(self) -> None:
        """Load built-in templates."""
        # These are embedded templates that ship with PromptC
        builtin = [
            {
                "id": "tutorial-python",
                "name": "Python Tutorial",
                "description": "Create comprehensive Python programming tutorials",
                "category": "tutorial",
                "tags": ["python", "programming", "education", "beginner"],
                "difficulty": "intermediate",
                "template": {
                    "persona": "expert Python instructor",
                    "intent": "teaching",
                    "domain": "programming",
                    "language": "python",
                    "level": "beginner",
                    "duration": "1 hour",
                },
                "examples": [
                    "Create a tutorial about Python lists and dictionaries",
                    "Write a beginner's guide to Python functions",
                ],
                "use_cases": [
                    "Educational content creation",
                    "Programming courses",
                    "Developer onboarding",
                ],
            },
            {
                "id": "api-documentation",
                "name": "API Documentation",
                "description": "Generate clear and comprehensive API documentation",
                "category": "documentation",
                "tags": ["api", "documentation", "technical", "reference"],
                "difficulty": "advanced",
                "template": {
                    "persona": "technical writer",
                    "intent": "documentation",
                    "domain": "software",
                    "style": "technical",
                    "format": "markdown",
                },
                "examples": [
                    "Document a REST API with authentication endpoints",
                    "Create API reference for payment gateway",
                ],
                "use_cases": [
                    "API documentation",
                    "Developer guides",
                    "Integration documentation",
                ],
            },
            {
                "id": "creative-story",
                "name": "Creative Story Writing",
                "description": "Write engaging creative stories and narratives",
                "category": "creative",
                "tags": ["story", "creative", "fiction", "narrative"],
                "difficulty": "beginner",
                "template": {
                    "persona": "creative writer",
                    "intent": "creative",
                    "domain": "fiction",
                    "tone": "engaging",
                    "length": "medium",
                },
                "examples": [
                    "Write a sci-fi short story about time travel",
                    "Create a fantasy adventure tale",
                ],
                "use_cases": [
                    "Content creation",
                    "Creative writing",
                    "Storytelling",
                ],
            },
            {
                "id": "technical-explanation",
                "name": "Technical Concept Explainer",
                "description": "Explain complex technical concepts in simple terms",
                "category": "technical",
                "tags": ["explanation", "technical", "education", "simplify"],
                "difficulty": "intermediate",
                "template": {
                    "persona": "technical educator",
                    "intent": "explanation",
                    "domain": "technology",
                    "level": "beginner",
                    "style": "simple",
                },
                "examples": [
                    "Explain how neural networks work to beginners",
                    "Describe blockchain technology in simple terms",
                ],
                "use_cases": [
                    "Technical education",
                    "Knowledge sharing",
                    "Onboarding materials",
                ],
            },
            {
                "id": "business-proposal",
                "name": "Business Proposal",
                "description": "Create professional business proposals and pitches",
                "category": "business",
                "tags": ["business", "proposal", "professional", "pitch"],
                "difficulty": "advanced",
                "template": {
                    "persona": "business consultant",
                    "intent": "proposal",
                    "domain": "business",
                    "tone": "professional",
                    "format": "structured",
                },
                "examples": [
                    "Write a project proposal for software development",
                    "Create a business partnership pitch",
                ],
                "use_cases": [
                    "Business development",
                    "Project proposals",
                    "Client pitches",
                ],
            },
            {
                "id": "code-review",
                "name": "Code Review Guide",
                "description": "Generate thorough code review checklists and guidelines",
                "category": "technical",
                "tags": ["code", "review", "quality", "best-practices"],
                "difficulty": "advanced",
                "template": {
                    "persona": "senior software engineer",
                    "intent": "review",
                    "domain": "software",
                    "focus": "quality",
                },
                "examples": [
                    "Create a Python code review checklist",
                    "Generate code review guidelines for security",
                ],
                "use_cases": [
                    "Code quality assurance",
                    "Team guidelines",
                    "Development standards",
                ],
            },
            {
                "id": "marketing-content",
                "name": "Marketing Content",
                "description": "Create compelling marketing and promotional content",
                "category": "business",
                "tags": ["marketing", "content", "promotion", "copywriting"],
                "difficulty": "intermediate",
                "template": {
                    "persona": "marketing specialist",
                    "intent": "promotion",
                    "domain": "marketing",
                    "tone": "persuasive",
                    "style": "engaging",
                },
                "examples": [
                    "Write a product launch announcement",
                    "Create social media campaign content",
                ],
                "use_cases": [
                    "Marketing campaigns",
                    "Product promotion",
                    "Brand content",
                ],
            },
            {
                "id": "data-analysis",
                "name": "Data Analysis Report",
                "description": "Generate data analysis reports with insights",
                "category": "technical",
                "tags": ["data", "analysis", "insights", "reporting"],
                "difficulty": "advanced",
                "template": {
                    "persona": "data analyst",
                    "intent": "analysis",
                    "domain": "data-science",
                    "format": "report",
                    "focus": "insights",
                },
                "examples": [
                    "Analyze sales data and provide insights",
                    "Create a customer behavior analysis report",
                ],
                "use_cases": [
                    "Business intelligence",
                    "Data reporting",
                    "Decision support",
                ],
            },
            {
                "id": "interview-prep",
                "name": "Interview Preparation",
                "description": "Create interview questions and preparation materials",
                "category": "education",
                "tags": ["interview", "preparation", "questions", "career"],
                "difficulty": "intermediate",
                "template": {
                    "persona": "career coach",
                    "intent": "preparation",
                    "domain": "professional",
                    "focus": "interview",
                },
                "examples": [
                    "Generate technical interview questions for Python developers",
                    "Create behavioral interview prep guide",
                ],
                "use_cases": [
                    "Hiring process",
                    "Career development",
                    "Interview practice",
                ],
            },
            {
                "id": "troubleshooting-guide",
                "name": "Troubleshooting Guide",
                "description": "Create step-by-step troubleshooting documentation",
                "category": "documentation",
                "tags": ["troubleshooting", "debug", "guide", "support"],
                "difficulty": "intermediate",
                "template": {
                    "persona": "support engineer",
                    "intent": "troubleshooting",
                    "domain": "technical",
                    "format": "step-by-step",
                },
                "examples": [
                    "Write a troubleshooting guide for database connection issues",
                    "Create a network debugging checklist",
                ],
                "use_cases": [
                    "Technical support",
                    "Documentation",
                    "Customer service",
                ],
            },
        ]

        for template_data in builtin:
            template = GalleryTemplate(**template_data)
            self.templates[template.id] = template

    def _load_template_file(self, file_path: Path) -> Optional[GalleryTemplate]:
        """Load template from YAML file."""
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            return None

        return GalleryTemplate(**data)

    def list_templates(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[GalleryTemplate]:
        """List templates with optional filtering.

        Args:
            category: Filter by category
            difficulty: Filter by difficulty level
            tags: Filter by tags (any match)

        Returns:
            List of matching templates
        """
        results = list(self.templates.values())

        if category:
            results = [t for t in results if t.category == category]

        if difficulty:
            results = [t for t in results if t.difficulty == difficulty]

        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]

        return sorted(results, key=lambda t: (t.category, t.name))

    def search_templates(self, query: str) -> List[GalleryTemplate]:
        """Search templates by query string.

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        return [t for t in self.templates.values() if t.matches_search(query)]

    def get_template(self, template_id: str) -> Optional[GalleryTemplate]:
        """Get template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template or None if not found
        """
        return self.templates.get(template_id)

    def get_categories(self) -> List[str]:
        """Get all available categories.

        Returns:
            List of unique categories
        """
        categories = {t.category for t in self.templates.values()}
        return sorted(categories)

    def add_custom_template(self, template: GalleryTemplate) -> None:
        """Add a custom template to the gallery.

        Args:
            template: Template to add
        """
        # Save to file
        template_file = self.gallery_dir / f"{template.id}.yaml"
        with open(template_file, "w", encoding="utf-8") as f:
            yaml.dump(template.to_dict(), f, default_flow_style=False)

        # Add to memory
        self.templates[template.id] = template

    def remove_custom_template(self, template_id: str) -> bool:
        """Remove a custom template.

        Args:
            template_id: Template ID to remove

        Returns:
            True if removed, False if not found or is built-in
        """
        template_file = self.gallery_dir / f"{template_id}.yaml"
        if not template_file.exists():
            return False

        template_file.unlink()
        if template_id in self.templates:
            del self.templates[template_id]

        return True

    def export_template(self, template_id: str, output_path: Path) -> bool:
        """Export template to file.

        Args:
            template_id: Template ID
            output_path: Output file path

        Returns:
            True if exported successfully
        """
        template = self.get_template(template_id)
        if not template:
            return False

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(template.to_dict(), f, default_flow_style=False)

        return True

    def import_template(self, file_path: Path) -> Optional[GalleryTemplate]:
        """Import template from file.

        Args:
            file_path: Path to template file

        Returns:
            Imported template or None if failed
        """
        try:
            template = self._load_template_file(file_path)
            if template:
                self.add_custom_template(template)
            return template
        except Exception:
            return None

    def get_template_preview(self, template_id: str) -> Optional[str]:
        """Get a formatted preview of a template.

        Args:
            template_id: Template ID

        Returns:
            Formatted preview string or None if not found
        """
        template = self.get_template(template_id)
        if not template:
            return None

        lines = [
            f"# {template.name}",
            "",
            f"**Category:** {template.category}",
            f"**Difficulty:** {template.difficulty}",
            f"**Tags:** {', '.join(template.tags)}",
            "",
            "## Description",
            template.description,
            "",
        ]

        if template.use_cases:
            lines.extend(
                [
                    "## Use Cases",
                    *[f"- {uc}" for uc in template.use_cases],
                    "",
                ]
            )

        if template.examples:
            lines.extend(
                [
                    "## Examples",
                    *[f"- {ex}" for ex in template.examples],
                    "",
                ]
            )

        lines.extend(
            [
                "## Template Fields",
                "```yaml",
                yaml.dump(template.template, default_flow_style=False).strip(),
                "```",
            ]
        )

        return "\n".join(lines)


# Singleton instance
_gallery: Optional[TemplateGallery] = None


def get_gallery(gallery_dir: Optional[Path] = None) -> TemplateGallery:
    """Get or create gallery instance.

    Args:
        gallery_dir: Optional custom gallery directory

    Returns:
        TemplateGallery instance
    """
    global _gallery
    if _gallery is None or gallery_dir is not None:
        _gallery = TemplateGallery(gallery_dir)
    return _gallery
