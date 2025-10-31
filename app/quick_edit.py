"""Quick edit functionality for prompts in history and favorites.

This module provides functionality to quickly edit prompts from history and favorites,
including text editing, metadata updates, and re-compilation.
"""

import tempfile
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from app.history import get_history_manager
from app.favorites import get_favorites_manager


console = Console()


class QuickEditor:
    """Quick editor for prompts in history and favorites."""

    def __init__(self):
        """Initialize quick editor with managers."""
        self.history_manager = get_history_manager()
        self.favorites_manager = get_favorites_manager()

    def find_prompt(self, prompt_id: str) -> tuple[Optional[Dict[str, Any]], Literal["history", "favorites", None]]:
        """Find a prompt by ID in history or favorites.

        Args:
            prompt_id: The prompt ID to find

        Returns:
            Tuple of (prompt_dict, source) where source is "history", "favorites", or None
        """
        # Search in history
        history_entry = self.history_manager.get_by_id(prompt_id)
        if history_entry:
            return history_entry.to_dict(), "history"

        # Search in favorites
        fav_entry = self.favorites_manager.get_by_id(prompt_id)
        if fav_entry:
            return fav_entry.to_dict(), "favorites"

        return None, None

    def get_editor(self) -> str:
        """Get the default text editor.

        Returns:
            Editor command
        """
        # Try environment variables
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        
        if editor:
            return editor

        # Platform-specific defaults
        if os.name == "nt":  # Windows
            return "notepad"
        else:  # Unix-like
            return "nano"

    def edit_text_in_editor(self, text: str) -> Optional[str]:
        """Open text in external editor and return edited content.

        Args:
            text: Initial text to edit

        Returns:
            Edited text or None if cancelled
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            temp_path = f.name

        try:
            editor = self.get_editor()
            
            # Open editor
            result = subprocess.run([editor, temp_path])
            
            if result.returncode != 0:
                console.print(f"[yellow]⚠️ Editor exited with code {result.returncode}[/yellow]")
                return None

            # Read edited content
            with open(temp_path, "r", encoding="utf-8") as f:
                edited_text = f.read()

            return edited_text

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

    def edit_prompt(self, prompt_id: str, recompile: bool = False) -> bool:
        """Edit a prompt by ID.

        Args:
            prompt_id: The prompt ID to edit
            recompile: Whether to recompile after editing

        Returns:
            True if edited successfully
        """
        # Find the prompt
        prompt_dict, source = self.find_prompt(prompt_id)

        if not prompt_dict or not source:
            console.print(f"\n[red]❌ Prompt not found:[/red] {prompt_id}\n")
            return False

        console.print(f"\n[cyan]✏️ Editing prompt from {source}:[/cyan] {prompt_id}\n")

        # Display current prompt info
        info_text = f"[bold cyan]ID:[/bold cyan] {prompt_dict.get('id', 'N/A')}\n"
        info_text += f"[bold cyan]Timestamp:[/bold cyan] {prompt_dict.get('timestamp', 'N/A')}\n"
        info_text += f"[bold cyan]Domain:[/bold cyan] {prompt_dict.get('domain', 'N/A')}\n"
        info_text += f"[bold cyan]Language:[/bold cyan] {prompt_dict.get('language', 'N/A')}\n"
        info_text += f"[bold cyan]Score:[/bold cyan] {prompt_dict.get('score', 0.0)}\n"

        console.print(Panel(info_text, title="📋 Current Prompt Info", border_style="cyan"))

        # Show what to edit
        console.print("\n[bold yellow]What would you like to edit?[/bold yellow]")
        console.print("1. Prompt text")
        console.print("2. Domain and Language")
        console.print("3. Tags")

        choice = Prompt.ask("\n[cyan]Choose option[/cyan]", choices=["1", "2", "3"], default="1")

        changes_made = False

        if choice == "1":
            # Edit prompt text
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
            # Edit domain and language
            console.print("\n[bold]Edit Domain and Language:[/bold]")
            
            new_domain = Prompt.ask("[cyan]Domain[/cyan]", default=prompt_dict.get("domain", "general"))
            new_language = Prompt.ask("[cyan]Language[/cyan]", default=prompt_dict.get("language", "en"))
            
            if new_domain != prompt_dict.get("domain", ""):
                prompt_dict["domain"] = new_domain
                changes_made = True
            if new_language != prompt_dict.get("language", ""):
                prompt_dict["language"] = new_language
                changes_made = True

        elif choice == "3":
            # Edit tags
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

        # Save changes
        if source == "history":
            # Update history entry
            for entry in self.history_manager.entries:
                if entry.id == prompt_id:
                    entry.prompt_text = prompt_dict.get("prompt_text", entry.prompt_text)
                    entry.domain = prompt_dict.get("domain", entry.domain)
                    entry.language = prompt_dict.get("language", entry.language)
                    entry.tags = prompt_dict.get("tags", entry.tags)
                    break
            self.history_manager._save()
        else:  # favorites
            # Update favorites entry
            for entry in self.favorites_manager.entries:
                if entry.id == prompt_id:
                    entry.prompt_text = prompt_dict.get("prompt_text", entry.prompt_text)
                    entry.domain = prompt_dict.get("domain", entry.domain)
                    entry.language = prompt_dict.get("language", entry.language)
                    entry.tags = prompt_dict.get("tags", entry.tags)
                    if hasattr(entry, 'notes'):
                        entry.notes = prompt_dict.get("notes", entry.notes)
                    break
            self.favorites_manager._save()

        console.print("\n[green]✅ Changes saved successfully![/green]\n")
        return True

    def display_prompt_preview(self, prompt: Dict[str, Any], source: str):
        """Display a preview of the prompt.

        Args:
            prompt: Prompt dictionary
            source: Source ("history" or "favorites")
        """
        info_text = f"[bold cyan]Source:[/bold cyan] {source}\n"
        info_text += f"[bold cyan]ID:[/bold cyan] {prompt.get('id', 'N/A')}\n"
        info_text += f"[bold cyan]Timestamp:[/bold cyan] {prompt.get('timestamp', 'N/A')}\n"
        info_text += f"[bold cyan]Domain:[/bold cyan] {prompt.get('domain', 'N/A')}\n"
        info_text += f"[bold cyan]Language:[/bold cyan] {prompt.get('language', 'N/A')}\n"

        if prompt.get("tags"):
            info_text += f"\n[bold magenta]Tags:[/bold magenta] {', '.join(prompt['tags'])}"

        console.print()
        console.print(Panel(info_text, title="📋 Prompt Info", border_style="cyan"))

        # Show input and output
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


# Singleton instance
_quick_editor: Optional[QuickEditor] = None


def get_quick_editor() -> QuickEditor:
    """Get or create the singleton QuickEditor instance.

    Returns:
        QuickEditor instance
    """
    global _quick_editor
    if _quick_editor is None:
        _quick_editor = QuickEditor()
    return _quick_editor
