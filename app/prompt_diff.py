"""Prompt comparison and diff functionality."""

import difflib
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.history import get_history_manager
from app.favorites import get_favorites_manager


class PromptComparison:
    """Handles prompt comparison and diff generation."""

    def __init__(self):
        """Initialize prompt comparison."""
        self.console = Console()
        self.history = get_history_manager()
        self.favorites = get_favorites_manager()

    def get_prompt_text(self, item_id: str, source: str = "auto") -> tuple[bool, str, str]:
        """Get prompt text from history or favorites.

        Args:
            item_id: Item identifier
            source: Source type ('history', 'favorites', or 'auto')

        Returns:
            Tuple of (success, text, actual_source)
        """
        if source == "favorites" or (source == "auto"):
            # Try favorites first - check both favorite ID and prompt ID
            fav = self.favorites.get_by_id(item_id)
            if fav:
                return True, fav.prompt_text, "favorites"

            # Also check by prompt_id
            for entry in self.favorites.entries:
                if entry.prompt_id == item_id:
                    return True, entry.prompt_text, "favorites"

        if source == "history" or (source == "auto"):
            # Try history
            hist = self.history.get_by_id(item_id)
            if hist:
                return True, hist.prompt_text, "history"

        return False, f"Item '{item_id}' not found", "none"

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0 to 100.0)
        """
        # Use SequenceMatcher for similarity
        matcher = difflib.SequenceMatcher(None, text1, text2)
        ratio = matcher.ratio()
        return ratio * 100.0

    def generate_diff(self, text1: str, text2: str, context_lines: int = 3) -> list[str]:
        """Generate unified diff between two texts.

        Args:
            text1: Original text
            text2: Modified text
            context_lines: Number of context lines

        Returns:
            List of diff lines
        """
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = difflib.unified_diff(
            lines1, lines2, fromfile="prompt1", tofile="prompt2", lineterm="", n=context_lines
        )

        return list(diff)

    def generate_side_by_side_diff(self, text1: str, text2: str) -> list[tuple[str, str, str]]:
        """Generate side-by-side diff with change markers.

        Args:
            text1: Original text
            text2: Modified text

        Returns:
            List of (marker, line1, line2) tuples
            Markers: ' ' (same), '-' (removed), '+' (added), '~' (changed)
        """
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        result = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    result.append((" ", lines1[i], lines2[j1 + i - i1]))
            elif tag == "delete":
                for i in range(i1, i2):
                    result.append(("-", lines1[i], ""))
            elif tag == "insert":
                for j in range(j1, j2):
                    result.append(("+", "", lines2[j]))
            elif tag == "replace":
                # Show as changed
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    line1 = lines1[i1 + k] if i1 + k < i2 else ""
                    line2 = lines2[j1 + k] if j1 + k < j2 else ""
                    result.append(("~", line1, line2))

        return result

    def get_diff_stats(self, text1: str, text2: str) -> dict[str, Any]:
        """Get statistics about the differences.

        Args:
            text1: Original text
            text2: Modified text

        Returns:
            Dictionary with diff statistics
        """
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        matcher = difflib.SequenceMatcher(None, lines1, lines2)

        stats = {
            "lines_added": 0,
            "lines_removed": 0,
            "lines_changed": 0,
            "lines_same": 0,
            "total_lines_1": len(lines1),
            "total_lines_2": len(lines2),
            "similarity": self.calculate_similarity(text1, text2),
        }

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                stats["lines_same"] += i2 - i1
            elif tag == "delete":
                stats["lines_removed"] += i2 - i1
            elif tag == "insert":
                stats["lines_added"] += j2 - j1
            elif tag == "replace":
                stats["lines_changed"] += max(i2 - i1, j2 - j1)

        return stats

    def display_comparison(
        self,
        id1: str,
        id2: str,
        source1: str = "auto",
        source2: str = "auto",
        show_side_by_side: bool = True,
    ) -> bool:
        """Display comparison between two prompts.

        Args:
            id1: First prompt ID
            id2: Second prompt ID
            source1: Source for first prompt
            source2: Source for second prompt
            show_side_by_side: Show side-by-side view

        Returns:
            True if successful, False otherwise
        """
        # Get both prompts
        success1, text1, actual_source1 = self.get_prompt_text(id1, source1)
        if not success1:
            self.console.print(f"[red]✗ {text1}[/red]")
            return False

        success2, text2, actual_source2 = self.get_prompt_text(id2, source2)
        if not success2:
            self.console.print(f"[red]✗ {text2}[/red]")
            return False

        # Calculate stats
        stats = self.get_diff_stats(text1, text2)

        # Display header
        self.console.print()
        self.console.print(
            Panel(
                f"[bold cyan]Prompt 1:[/] {id1} [dim]({actual_source1})[/dim]\n"
                f"[bold cyan]Prompt 2:[/] {id2} [dim]({actual_source2})[/dim]",
                title="📊 Prompt Comparison",
                border_style="cyan",
            )
        )

        # Display statistics
        self.console.print()
        stats_table = Table(title="Comparison Statistics", show_header=False)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="yellow")

        stats_table.add_row("Similarity Score", f"{stats['similarity']:.2f}%")
        stats_table.add_row("Lines in Prompt 1", str(stats["total_lines_1"]))
        stats_table.add_row("Lines in Prompt 2", str(stats["total_lines_2"]))
        stats_table.add_row("Lines Same", f"{stats['lines_same']} ✓")
        stats_table.add_row("Lines Changed", f"{stats['lines_changed']} ~")
        stats_table.add_row("Lines Added", f"{stats['lines_added']} +")
        stats_table.add_row("Lines Removed", f"{stats['lines_removed']} -")

        self.console.print(stats_table)
        self.console.print()

        # Display diff
        if show_side_by_side:
            self._display_side_by_side(text1, text2, id1, id2)
        else:
            self._display_unified_diff(text1, text2)

        return True

    def _display_side_by_side(self, text1: str, text2: str, id1: str, id2: str) -> None:
        """Display side-by-side diff."""
        diff_lines = self.generate_side_by_side_diff(text1, text2)

        # Create table for side-by-side view
        table = Table(title="Side-by-Side Comparison", show_header=True, expand=True)
        table.add_column("", style="dim", width=2)
        table.add_column(f"Prompt 1 ({id1})", style="cyan", width=50)
        table.add_column(f"Prompt 2 ({id2})", style="green", width=50)

        for marker, line1, line2 in diff_lines[:50]:  # Limit to 50 lines
            if marker == " ":
                # Same line
                table.add_row(" ", line1, line2)
            elif marker == "-":
                # Removed line
                table.add_row("-", f"[red]{line1}[/red]", "[dim]---[/dim]")
            elif marker == "+":
                # Added line
                table.add_row("+", "[dim]---[/dim]", f"[green]{line2}[/green]")
            elif marker == "~":
                # Changed line
                table.add_row("~", f"[yellow]{line1}[/yellow]", f"[yellow]{line2}[/yellow]")

        self.console.print(table)

        if len(diff_lines) > 50:
            self.console.print(
                f"[dim]... {len(diff_lines) - 50} more lines (showing first 50)[/dim]"
            )

    def _display_unified_diff(self, text1: str, text2: str) -> None:
        """Display unified diff format."""
        diff_lines = self.generate_diff(text1, text2)

        self.console.print("[bold]Unified Diff:[/]")
        self.console.print()

        for line in diff_lines[:100]:  # Limit to 100 lines
            if line.startswith("+++") or line.startswith("---"):
                self.console.print(f"[cyan]{line}[/cyan]")
            elif line.startswith("+"):
                self.console.print(f"[green]{line}[/green]")
            elif line.startswith("-"):
                self.console.print(f"[red]{line}[/red]")
            elif line.startswith("@@"):
                self.console.print(f"[yellow]{line}[/yellow]")
            else:
                self.console.print(line)

        if len(diff_lines) > 100:
            self.console.print(
                f"[dim]... {len(diff_lines) - 100} more lines (showing first 100)[/dim]"
            )


# Singleton instance
_prompt_comparison: PromptComparison | None = None


def get_prompt_comparison() -> PromptComparison:
    """Get the singleton prompt comparison instance.

    Returns:
        PromptComparison instance
    """
    global _prompt_comparison
    if _prompt_comparison is None:
        _prompt_comparison = PromptComparison()
    return _prompt_comparison
