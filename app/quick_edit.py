"""Quick edit functionality for prompts in history and favorites.

This module provides functionality to quickly edit prompts from history and favorites,
including text editing, metadata updates, and re-compilation.
"""

import os
import shlex
import click
from typing import Any, Dict, Literal, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

# from app.history import get_history_manager
from app.favorites import get_favorites_manager


def get_history_manager():
    """Stub for removed history manager."""

    class HistoryManagerStub:
        def get_by_id(self, *args, **kwargs):
            return None

        def _save(self):
            pass

        @property
        def entries(self):
            return []

    return HistoryManagerStub()


console = Console()

FORBIDDEN_EDITOR_PREFIXES = (
    "bash",
    "sh",
    "zsh",
    "csh",
    "ksh",
    "tcsh",
    "dash",
    "fish",
    "python",
    "pypy",
    "env",
    "cmd",
    "powershell",
    "pwsh",
    "node",
    "ruby",
    "perl",
    "php",
)
SHELL_METACHAR_TOKENS = {";", "|", "&", "&&", "||"}


class QuickEditor:
    """Quick editor for prompts in history and favorites."""

    def __init__(self):
        """Initialize quick editor with managers."""
        self.history_manager = get_history_manager()
        self.favorites_manager = get_favorites_manager()

    def find_prompt(
        self, prompt_id: str
    ) -> tuple[Optional[Dict[str, Any]], Literal["history", "favorites", None]]:
        """Find a prompt by ID in history or favorites.

        Args:
            prompt_id: The prompt ID to find

        Returns:
            Tuple of (prompt_dict, source) where source is "history", "favorites", or None
        """
        history_entry = self.history_manager.get_by_id(prompt_id)
        if history_entry:
            return history_entry.to_dict(), "history"

        fav_entry = self.favorites_manager.get_by_id(prompt_id)
        if fav_entry:
            return fav_entry.to_dict(), "favorites"

        return None, None

    def get_editor(self) -> str:
        """Get the default text editor."""
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if editor:
            return editor

        return "notepad" if os.name == "nt" else "nano"

    def _parse_editor_command(self, editor: str) -> Optional[list[str]]:
        """Parse and validate the configured editor command."""
        try:
            editor_parts = shlex.split(editor, posix=os.name != "nt")
        except ValueError as exc:
            console.print(f"[red]⚠️ Failed to parse editor command from EDITOR/VISUAL: {exc}[/red]")
            return None

        if os.name == "nt":
            editor_parts = [
                part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part
                for part in editor_parts
            ]

        editor_parts = [part for part in editor_parts if part]
        if not editor_parts:
            console.print("[red]⚠️ EDITOR/VISUAL environment variable is empty or invalid.[/red]")
            return None

        for part in editor_parts:
            if part in SHELL_METACHAR_TOKENS:
                console.print(
                    f"[red]⚠️ Editor command contains forbidden shell operator: {part}[/red]"
                )
                return None

            normalized_part = part.replace("\\", "/")
            basename = os.path.basename(normalized_part).lower()
            base_without_ext = basename[:-4] if basename.endswith(".exe") else basename

            for prefix in FORBIDDEN_EDITOR_PREFIXES:
                if base_without_ext.startswith(prefix):
                    remainder = base_without_ext[len(prefix) :]
                    if not remainder or remainder.lstrip(".0123456789") == "":
                        console.print(
                            f"[red]⚠️ Editor command contains forbidden executable or shell: {part}[/red]"
                        )
                        return None

        return editor_parts

    def edit_text_in_editor(self, text: str) -> Optional[str]:
        """Open text in external editor and return edited content."""
        try:
            editor_parts = self._parse_editor_command(self.get_editor())
            if not editor_parts:
                return None

            # Reconstruct the editor string safely for cross-platform click.edit
            # shlex.join uses POSIX quotes which break Windows click.edit parsing
            if os.name == "nt":
                # For Windows, manually quote parts with spaces using double quotes
                safe_editor = " ".join(
                    f'"{part}"' if " " in part else part for part in editor_parts
                )
            else:
                safe_editor = shlex.join(editor_parts)

            try:
                return click.edit(text, editor=safe_editor, require_save=True)
            except click.ClickException as e:
                console.print(f"[yellow]⚠️ Editor failed: {e}[/yellow]")
                return None
        except Exception as exc:
            console.print(f"[red]⚠️ Unexpected editor error: {exc}[/red]")
            return None

    def edit_prompt(self, prompt_id: str, recompile: bool = False) -> bool:
        """Edit a prompt by ID."""
        prompt_dict, source = self.find_prompt(prompt_id)

        if not prompt_dict or not source:
            console.print(f"\n[red]❌ Prompt not found:[/red] {prompt_id}\n")
            return False

        console.print(f"\n[cyan]✏️ Editing prompt from {source}:[/cyan] {prompt_id}\n")

        info_text = f"[bold cyan]ID:[/bold cyan] {prompt_dict.get('id', 'N/A')}\n"
        info_text += f"[bold cyan]Timestamp:[/bold cyan] {prompt_dict.get('timestamp', 'N/A')}\n"
        info_text += f"[bold cyan]Domain:[/bold cyan] {prompt_dict.get('domain', 'N/A')}\n"
        info_text += f"[bold cyan]Language:[/bold cyan] {prompt_dict.get('language', 'N/A')}\n"
        info_text += f"[bold cyan]Score:[/bold cyan] {prompt_dict.get('score', 0.0)}\n"

        console.print(Panel(info_text, title="📋 Current Prompt Info", border_style="cyan"))

        console.print("\n[bold yellow]What would you like to edit?[/bold yellow]")
        console.print("1. Prompt text")
        console.print("2. Domain and Language")
        console.print("3. Tags")

        choice = Prompt.ask("\n[cyan]Choose option[/cyan]", choices=["1", "2", "3"], default="1")

        changes_made = False

        if choice == "1":
            current_text = prompt_dict.get("prompt_text", "")
            console.print(f"\n[dim]Current text:[/dim]\n{current_text[:200]}...\n")

            if Confirm.ask("Edit in external editor?", default=True):
                edited_text = self.edit_text_in_editor(current_text)
                if edited_text and edited_text != current_text:
                    prompt_dict["prompt_text"] = edited_text
                    changes_made = True
            else:
                new_text = Prompt.ask("[cyan]Enter new text[/cyan]", default=current_text[:100])
                if new_text != current_text:
                    prompt_dict["prompt_text"] = new_text
                    changes_made = True

        elif choice == "2":
            console.print("\n[bold]Edit Domain and Language:[/bold]")

            new_domain = Prompt.ask(
                "[cyan]Domain[/cyan]", default=prompt_dict.get("domain", "general")
            )
            new_language = Prompt.ask(
                "[cyan]Language[/cyan]", default=prompt_dict.get("language", "en")
            )

            if new_domain != prompt_dict.get("domain", ""):
                prompt_dict["domain"] = new_domain
                changes_made = True
            if new_language != prompt_dict.get("language", ""):
                prompt_dict["language"] = new_language
                changes_made = True

        elif choice == "3":
            console.print("\n[bold]Edit Tags:[/bold]")

            current_tags = ", ".join(prompt_dict.get("tags", []))
            new_tags_str = Prompt.ask("[cyan]Tags (comma-separated)[/cyan]", default=current_tags)
            new_tags = [tag.strip() for tag in new_tags_str.split(",") if tag.strip()]

            if new_tags != prompt_dict.get("tags", []):
                prompt_dict["tags"] = new_tags
                changes_made = True

        if not changes_made:
            console.print("\n[yellow]No changes made[/yellow]\n")
            return False

        if source == "history":
            for entry in self.history_manager.entries:
                if entry.id == prompt_id:
                    entry.prompt_text = prompt_dict.get("prompt_text", entry.prompt_text)
                    entry.domain = prompt_dict.get("domain", entry.domain)
                    entry.language = prompt_dict.get("language", entry.language)
                    entry.tags = prompt_dict.get("tags", entry.tags)
                    break
            self.history_manager._save()
        else:
            for entry in self.favorites_manager.entries:
                if entry.id == prompt_id:
                    entry.prompt_text = prompt_dict.get("prompt_text", entry.prompt_text)
                    entry.domain = prompt_dict.get("domain", entry.domain)
                    entry.language = prompt_dict.get("language", entry.language)
                    entry.tags = prompt_dict.get("tags", entry.tags)
                    if hasattr(entry, "notes"):
                        entry.notes = prompt_dict.get("notes", entry.notes)
                    break
            self.favorites_manager._save()

        console.print("\n[green]✅ Changes saved successfully![/green]\n")
        return True

    def display_prompt_preview(self, prompt: Dict[str, Any], source: str):
        """Display a preview of the prompt."""
        info_text = f"[bold cyan]Source:[/bold cyan] {source}\n"
        info_text += f"[bold cyan]ID:[/bold cyan] {prompt.get('id', 'N/A')}\n"
        info_text += f"[bold cyan]Timestamp:[/bold cyan] {prompt.get('timestamp', 'N/A')}\n"
        info_text += f"[bold cyan]Domain:[/bold cyan] {prompt.get('domain', 'N/A')}\n"
        info_text += f"[bold cyan]Language:[/bold cyan] {prompt.get('language', 'N/A')}\n"

        if prompt.get("tags"):
            info_text += f"\n[bold magenta]Tags:[/bold magenta] {', '.join(prompt['tags'])}"

        console.print()
        console.print(Panel(info_text, title="📋 Prompt Info", border_style="cyan"))

        input_text = prompt.get("input_text", "")
        output_text = prompt.get("output_prompt", "")

        if input_text:
            preview = input_text[:200] + "..." if len(input_text) > 200 else input_text
            console.print()
            console.print(Panel(preview, title="Input Text", border_style="blue"))

        if output_text:
            preview = output_text[:300] + "..." if len(output_text) > 300 else output_text
            console.print()
            console.print(Panel(preview, title="Output Prompt", border_style="green"))

        console.print()


_quick_editor: Optional[QuickEditor] = None


def get_quick_editor() -> QuickEditor:
    """Get or create the singleton QuickEditor instance."""
    global _quick_editor
    if _quick_editor is None:
        _quick_editor = QuickEditor()
    return _quick_editor
