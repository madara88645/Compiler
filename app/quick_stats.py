"""Quick statistics and counters for prompts."""

from datetime import datetime, timedelta
from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from app.history import get_history_manager
from app.favorites import get_favorites_manager


class QuickStats:
    """Quick statistics calculator for prompts."""

    def __init__(self):
        """Initialize quick stats."""
        self.console = Console()
        self.history = get_history_manager()
        self.favorites = get_favorites_manager()

    def get_counts(self) -> Dict[str, int]:
        """Get basic counts.

        Returns:
            Dict with history, favorites, and total counts
        """
        history_count = len(self.history.entries)
        favorites_count = len(self.favorites.entries)

        return {
            "history": history_count,
            "favorites": favorites_count,
            "total": history_count + favorites_count,
        }

    def get_recent_activity(self, days: int = 7) -> Dict[str, Any]:
        """Get recent activity statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dict with recent activity stats
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Count recent history entries
        recent_history = 0
        for entry in self.history.entries:
            try:
                entry_date = datetime.fromisoformat(entry.timestamp)
                if entry_date >= cutoff_date:
                    recent_history += 1
            except (ValueError, AttributeError):
                continue

        # Count recent favorites
        recent_favorites = 0
        for entry in self.favorites.entries:
            try:
                entry_date = datetime.fromisoformat(entry.timestamp)
                if entry_date >= cutoff_date:
                    recent_favorites += 1
            except (ValueError, AttributeError):
                continue

        return {
            "days": days,
            "history": recent_history,
            "favorites": recent_favorites,
            "total": recent_history + recent_favorites,
        }

    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get quality metrics based on scores.

        Returns:
            Dict with quality statistics
        """
        # Collect all scores
        all_scores = []

        for entry in self.history.entries:
            if entry.score > 0:
                all_scores.append(entry.score)

        for entry in self.favorites.entries:
            if entry.score > 0:
                all_scores.append(entry.score)

        if not all_scores:
            return {
                "average": 0.0,
                "high_quality": 0,
                "high_quality_percentage": 0.0,
                "total_rated": 0,
            }

        average_score = sum(all_scores) / len(all_scores)
        high_quality = sum(1 for score in all_scores if score >= 0.8)
        high_quality_percentage = (high_quality / len(all_scores)) * 100

        return {
            "average": round(average_score, 2),
            "high_quality": high_quality,
            "high_quality_percentage": round(high_quality_percentage, 1),
            "total_rated": len(all_scores),
        }

    def get_top_domains(self, limit: int = 5) -> list:
        """Get top domains by usage.

        Args:
            limit: Maximum number of domains to return

        Returns:
            List of tuples (domain, count)
        """
        domain_counts = {}

        for entry in self.history.entries:
            domain = entry.domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        for entry in self.favorites.entries:
            domain = entry.domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Sort by count descending
        sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_domains[:limit]

    def get_language_distribution(self) -> Dict[str, int]:
        """Get language distribution.

        Returns:
            Dict with language counts
        """
        language_counts = {}

        for entry in self.history.entries:
            lang = entry.language
            language_counts[lang] = language_counts.get(lang, 0) + 1

        for entry in self.favorites.entries:
            lang = entry.language
            language_counts[lang] = language_counts.get(lang, 0) + 1

        return language_counts

    def create_banner(self, compact: bool = False) -> str:
        """Create statistics banner.

        Args:
            compact: If True, create a compact single-line banner

        Returns:
            Formatted banner string
        """
        counts = self.get_counts()
        recent = self.get_recent_activity(7)
        quality = self.get_quality_metrics()

        if compact:
            # Single line compact banner
            return (
                f"📊 [cyan]{counts['total']}[/cyan] prompts "
                f"([green]{counts['history']}[/green] history, "
                f"[magenta]{counts['favorites']}[/magenta] favorites) • "
                f"[yellow]{recent['total']}[/yellow] in last 7 days • "
                f"⭐ [yellow]{quality['average']:.2f}[/yellow] avg score"
            )
        else:
            # Multi-line detailed banner
            lines = [
                "[bold cyan]📊 Prompt Statistics[/bold cyan]",
                "",
                f"Total Prompts:    [cyan]{counts['total']:4}[/cyan]",
                f"  History:        [green]{counts['history']:4}[/green]",
                f"  Favorites:      [magenta]{counts['favorites']:4}[/magenta]",
                "",
                f"Recent (7 days):  [yellow]{recent['total']:4}[/yellow]",
                f"Average Score:    [yellow]{quality['average']:.2f}[/yellow]",
            ]

            if quality['total_rated'] > 0:
                lines.append(
                    f"High Quality:     [green]{quality['high_quality_percentage']:.1f}%[/green]"
                )

            return "\n".join(lines)

    def display_full_stats(self) -> None:
        """Display comprehensive statistics in a formatted panel."""
        counts = self.get_counts()
        recent_7d = self.get_recent_activity(7)
        recent_30d = self.get_recent_activity(30)
        quality = self.get_quality_metrics()
        top_domains = self.get_top_domains(5)
        languages = self.get_language_distribution()

        # Create main stats panel
        content = Text()
        content.append("📊 PROMPT STATISTICS\n\n", style="bold cyan")

        # Counts section
        content.append("Overall Counts:\n", style="bold white")
        content.append(f"  Total Prompts:  ", style="white")
        content.append(f"{counts['total']:4}\n", style="cyan bold")
        content.append(f"  History:        ", style="white")
        content.append(f"{counts['history']:4}\n", style="green")
        content.append(f"  Favorites:      ", style="white")
        content.append(f"{counts['favorites']:4}\n\n", style="magenta")

        # Recent activity section
        content.append("Recent Activity:\n", style="bold white")
        content.append(f"  Last 7 days:    ", style="white")
        content.append(f"{recent_7d['total']:4}\n", style="yellow")
        content.append(f"  Last 30 days:   ", style="white")
        content.append(f"{recent_30d['total']:4}\n\n", style="yellow")

        # Quality metrics section
        content.append("Quality Metrics:\n", style="bold white")
        content.append(f"  Average Score:  ", style="white")
        content.append(f"{quality['average']:.2f}\n", style="yellow")
        if quality['total_rated'] > 0:
            content.append(f"  High Quality:   ", style="white")
            content.append(f"{quality['high_quality_percentage']:.1f}%\n", style="green")
            content.append(f"  Total Rated:    ", style="white")
            content.append(f"{quality['total_rated']}\n\n", style="cyan")

        # Top domains section
        if top_domains:
            content.append("Top Domains:\n", style="bold white")
            for i, (domain, count) in enumerate(top_domains, 1):
                bar = "█" * min(count // 2, 20)
                content.append(f"  {i}. {domain:15} ", style="white")
                content.append(f"[{count:3}] ", style="cyan")
                content.append(f"{bar}\n", style="yellow")
            content.append("\n")

        # Languages section
        if languages:
            content.append("Languages:\n", style="bold white")
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            for lang, count in sorted_langs[:3]:
                content.append(f"  {lang.upper():5} ", style="white")
                content.append(f"{count:4}\n", style="cyan")

        panel = Panel(
            content,
            title="[bold green]PromptC Statistics[/bold green]",
            border_style="green",
            padding=(1, 2),
        )

        self.console.print(panel)

    def display_compact_table(self) -> None:
        """Display compact statistics table."""
        counts = self.get_counts()
        recent = self.get_recent_activity(7)
        quality = self.get_quality_metrics()

        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Metric", style="white", no_wrap=True)
        table.add_column("Value", style="cyan bold", justify="right")

        table.add_row("Total Prompts", f"{counts['total']}")
        table.add_row("├─ History", f"[green]{counts['history']}[/green]")
        table.add_row("└─ Favorites", f"[magenta]{counts['favorites']}[/magenta]")
        table.add_row("", "")
        table.add_row("Last 7 Days", f"[yellow]{recent['total']}[/yellow]")
        table.add_row("Avg Score", f"[yellow]{quality['average']:.2f}[/yellow]")

        if quality['total_rated'] > 0:
            table.add_row(
                "High Quality", f"[green]{quality['high_quality_percentage']:.1f}%[/green]"
            )

        self.console.print(table)


# Singleton instance
_quick_stats_instance = None


def get_quick_stats() -> QuickStats:
    """Get singleton instance of QuickStats.

    Returns:
        QuickStats instance
    """
    global _quick_stats_instance
    if _quick_stats_instance is None:
        _quick_stats_instance = QuickStats()
    return _quick_stats_instance
