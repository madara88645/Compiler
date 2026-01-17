"""Template preview and variable filling functionality."""

import re

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

from app.templates_manager import get_templates_manager


class TemplatePreview:
    """Handles template preview and variable filling."""

    def __init__(self):
        """Initialize template preview handler."""
        self.console = Console()
        self.templates = get_templates_manager()

    def extract_variables(self, template_content: str) -> list[str]:
        """Extract variable names from template content.

        Args:
            template_content: Template text with {{variable}} placeholders

        Returns:
            List of unique variable names found in template
        """
        pattern = r"\{\{(\w+)\}\}"
        variables = re.findall(pattern, template_content)
        return list(dict.fromkeys(variables))  # Remove duplicates, preserve order

    def validate_variables(
        self, template_content: str, variables: dict[str, str]
    ) -> tuple[bool, list[str]]:
        """Validate that all required variables are provided.

        Args:
            template_content: Template text
            variables: Dictionary of variable values

        Returns:
            Tuple of (is_valid, missing_variables)
        """
        required = self.extract_variables(template_content)
        missing = [var for var in required if var not in variables or not variables[var]]
        return len(missing) == 0, missing

    def fill_template(self, template_content: str, variables: dict[str, str]) -> str:
        """Fill template with variable values.

        Args:
            template_content: Template text with placeholders
            variables: Dictionary mapping variable names to values

        Returns:
            Filled template text
        """
        result = template_content
        for var_name, var_value in variables.items():
            pattern = r"\{\{" + re.escape(var_name) + r"\}\}"
            result = re.sub(pattern, var_value, result)
        return result

    def preview_template(
        self, template_id: str, variables: dict[str, str] | None = None
    ) -> tuple[bool, str]:
        """Preview a template with variable information.

        Args:
            template_id: Template identifier
            variables: Optional dictionary of variable values for preview

        Returns:
            Tuple of (success, message)
        """
        template = self.templates.get_template(template_id)
        if not template:
            return False, f"Template '{template_id}' not found"

        content = template.template_text
        required_vars = self.extract_variables(content)

        # Show template info
        self.console.print(
            Panel(
                f"[bold cyan]{template.name}[/bold cyan]\n[dim]{template.description}[/dim]",
                title="📄 Template",
                border_style="cyan",
            )
        )

        # Show variables table
        if required_vars:
            table = Table(title="Required Variables", show_header=True)
            table.add_column("Variable", style="yellow")
            table.add_column("Value", style="green")
            table.add_column("Status", style="magenta")

            for var in required_vars:
                value = variables.get(var, "") if variables else ""
                status = "✓ Provided" if value else "⚠ Missing"
                display_value = value if value else "[dim]not set[/dim]"
                table.add_row(var, display_value, status)

            self.console.print(table)
            self.console.print()

        # Show preview
        if variables:
            is_valid, missing = self.validate_variables(content, variables)
            if not is_valid:
                self.console.print(f"[yellow]⚠ Missing variables: {', '.join(missing)}[/yellow]\n")

            filled = self.fill_template(content, variables)
            self.console.print(
                Panel(
                    Syntax(filled, "markdown", theme="monokai", line_numbers=False),
                    title="👁 Preview",
                    border_style="green",
                )
            )
        else:
            self.console.print(
                Panel(
                    Syntax(content, "markdown", theme="monokai", line_numbers=False),
                    title="📝 Template Content",
                    border_style="blue",
                )
            )

        return True, "Preview displayed"

    def interactive_fill(self, template_id: str) -> tuple[bool, str, dict[str, str]]:
        """Interactively fill template variables.

        Args:
            template_id: Template identifier

        Returns:
            Tuple of (success, filled_content, variables_used)
        """
        template = self.templates.get_template(template_id)
        if not template:
            return False, f"Template '{template_id}' not found", {}

        content = template.template_text
        required_vars = self.extract_variables(content)

        if not required_vars:
            self.console.print("[yellow]⚠ This template has no variables to fill[/yellow]")
            return True, content, {}

        self.console.print(
            Panel(
                f"[bold cyan]{template.name}[/bold cyan]\n[dim]Fill in the variables below[/dim]",
                title="📝 Interactive Template Fill",
                border_style="cyan",
            )
        )

        variables = {}
        for var_name in required_vars:
            value = Prompt.ask(f"[yellow]Enter value for[/yellow] [bold]{var_name}[/bold]")
            variables[var_name] = value

        filled = self.fill_template(content, variables)

        self.console.print()
        self.console.print(
            Panel(
                Syntax(filled, "markdown", theme="monokai", line_numbers=False),
                title="✓ Filled Template",
                border_style="green",
            )
        )

        return True, filled, variables


# Singleton instance
_template_preview: TemplatePreview | None = None


def get_template_preview() -> TemplatePreview:
    """Get the singleton template preview instance.

    Returns:
        TemplatePreview instance
    """
    global _template_preview
    if _template_preview is None:
        _template_preview = TemplatePreview()
    return _template_preview
