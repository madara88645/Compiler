"""Advanced search functionality for prompts with filtering and fuzzy matching."""

import re
from datetime import datetime
from typing import Any, List, Optional, Dict, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.history import get_history_manager, HistoryEntry
from app.favorites import get_favorites_manager, FavoriteEntry


class AdvancedSearch:
    """Handles advanced search with multiple filters and fuzzy matching."""

    def __init__(self):
        """Initialize advanced search."""
        self.console = Console()
        self.history = get_history_manager()
        self.favorites = get_favorites_manager()

    def fuzzy_match(self, text: str, query: str, threshold: float = 0.6) -> bool:
        """Check if text fuzzy matches query.

        Args:
            text: Text to search in
            query: Search query
            threshold: Minimum similarity threshold (0.0 to 1.0)

        Returns:
            True if fuzzy match found
        """
        if not query or not text:
            return False

        text_lower = text.lower()
        query_lower = query.lower()

        # Exact substring match
        if query_lower in text_lower:
            return True

        # Simple fuzzy matching - check character overlap
        query_chars = set(query_lower)
        text_chars = set(text_lower)
        overlap = len(query_chars & text_chars)
        similarity = overlap / len(query_chars) if query_chars else 0

        return similarity >= threshold

    def regex_match(self, text: str, pattern: str) -> bool:
        """Check if text matches regex pattern.

        Args:
            text: Text to search in
            pattern: Regex pattern

        Returns:
            True if pattern matches
        """
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False

    def match_date_range(
        self,
        timestamp: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> bool:
        """Check if timestamp falls within date range.

        Args:
            timestamp: ISO format timestamp
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            True if within range
        """
        try:
            entry_date = datetime.fromisoformat(timestamp).date()

            if start_date:
                start = datetime.fromisoformat(start_date).date()
                if entry_date < start:
                    return False

            if end_date:
                end = datetime.fromisoformat(end_date).date()
                if entry_date > end:
                    return False

            return True
        except (ValueError, AttributeError):
            return True  # If parsing fails, include the entry

    def search_history(
        self,
        query: Optional[str] = None,
        domain: Optional[str] = None,
        language: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_regex: bool = False,
        use_fuzzy: bool = False,
        min_score: Optional[float] = None,
        max_results: int = 50,
    ) -> List[HistoryEntry]:
        """Search history with advanced filters.

        Args:
            query: Text search query
            domain: Filter by domain
            language: Filter by language
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_regex: Use regex matching
            use_fuzzy: Use fuzzy matching
            min_score: Minimum score threshold
            max_results: Maximum number of results

        Returns:
            List of matching history entries
        """
        results = []

        for entry in self.history.entries:
            # Domain filter
            if domain and entry.domain != domain:
                continue

            # Language filter
            if language and entry.language != language:
                continue

            # Date range filter
            if not self.match_date_range(entry.timestamp, start_date, end_date):
                continue

            # Score filter
            if min_score is not None and entry.score < min_score:
                continue

            # Text query filter
            if query:
                if use_regex:
                    if not self.regex_match(entry.prompt_text, query):
                        continue
                elif use_fuzzy:
                    if not self.fuzzy_match(entry.prompt_text, query):
                        continue
                else:
                    if query.lower() not in entry.prompt_text.lower():
                        continue

            results.append(entry)

            if len(results) >= max_results:
                break

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results

    def search_favorites(
        self,
        query: Optional[str] = None,
        domain: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_regex: bool = False,
        use_fuzzy: bool = False,
        min_score: Optional[float] = None,
        max_results: int = 50,
    ) -> List[FavoriteEntry]:
        """Search favorites with advanced filters.

        Args:
            query: Text search query
            domain: Filter by domain
            language: Filter by language
            tags: Filter by tags (any match)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_regex: Use regex matching
            use_fuzzy: Use fuzzy matching
            min_score: Minimum score threshold
            max_results: Maximum number of results

        Returns:
            List of matching favorite entries
        """
        results = []

        for entry in self.favorites.entries:
            # Domain filter
            if domain and entry.domain != domain:
                continue

            # Language filter
            if language and entry.language != language:
                continue

            # Tags filter
            if tags and not any(tag in entry.tags for tag in tags):
                continue

            # Date range filter
            if not self.match_date_range(entry.timestamp, start_date, end_date):
                continue

            # Score filter
            if min_score is not None and entry.score < min_score:
                continue

            # Text query filter (search in prompt text and notes)
            if query:
                search_text = f"{entry.prompt_text} {entry.notes}"
                if use_regex:
                    if not self.regex_match(search_text, query):
                        continue
                elif use_fuzzy:
                    if not self.fuzzy_match(search_text, query):
                        continue
                else:
                    if query.lower() not in search_text.lower():
                        continue

            results.append(entry)

            if len(results) >= max_results:
                break

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results

    def search_all(
        self,
        query: Optional[str] = None,
        domain: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_regex: bool = False,
        use_fuzzy: bool = False,
        min_score: Optional[float] = None,
        max_results: int = 50,
    ) -> Dict[str, List[Union[HistoryEntry, FavoriteEntry]]]:
        """Search both history and favorites.

        Args:
            query: Text search query
            domain: Filter by domain
            language: Filter by language
            tags: Filter by tags (favorites only)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_regex: Use regex matching
            use_fuzzy: Use fuzzy matching
            min_score: Minimum score threshold
            max_results: Maximum number of results per source

        Returns:
            Dict with 'history' and 'favorites' keys containing results
        """
        history_results = self.search_history(
            query=query,
            domain=domain,
            language=language,
            start_date=start_date,
            end_date=end_date,
            use_regex=use_regex,
            use_fuzzy=use_fuzzy,
            min_score=min_score,
            max_results=max_results,
        )

        favorites_results = self.search_favorites(
            query=query,
            domain=domain,
            language=language,
            tags=tags,
            start_date=start_date,
            end_date=end_date,
            use_regex=use_regex,
            use_fuzzy=use_fuzzy,
            min_score=min_score,
            max_results=max_results,
        )

        return {"history": history_results, "favorites": favorites_results}

    def display_results(
        self,
        results: Dict[str, List[Union[HistoryEntry, FavoriteEntry]]],
        show_full_text: bool = False,
    ) -> None:
        """Display search results in a formatted table.

        Args:
            results: Dict with 'history' and 'favorites' results
            show_full_text: Show full prompt text instead of truncated
        """
        history_results = results.get("history", [])
        favorites_results = results.get("favorites", [])

        total_results = len(history_results) + len(favorites_results)

        if total_results == 0:
            self.console.print(
                Panel(
                    "[yellow]No results found[/yellow]",
                    title="Search Results",
                    border_style="yellow",
                )
            )
            return

        # Display summary
        summary = Text()
        summary.append(f"Found {total_results} results\n", style="bold green")
        summary.append(f"  • History: {len(history_results)}\n", style="cyan")
        summary.append(f"  • Favorites: {len(favorites_results)}", style="magenta")

        self.console.print(Panel(summary, title="Search Results", border_style="green"))

        # Display history results
        if history_results:
            self.console.print("\n[bold cyan]History Results:[/bold cyan]")
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("ID", style="dim", width=12)
            table.add_column("Domain", width=12)
            table.add_column("Language", width=8)
            table.add_column("Score", width=6)
            table.add_column("Date", width=10)
            table.add_column("Prompt", width=50 if not show_full_text else None)

            for entry in history_results[:20]:  # Limit display to 20
                date = datetime.fromisoformat(entry.timestamp).strftime("%Y-%m-%d")
                prompt_text = (
                    entry.prompt_text
                    if show_full_text
                    else entry.prompt_text[:47] + "..."
                    if len(entry.prompt_text) > 50
                    else entry.prompt_text
                )

                table.add_row(
                    entry.id[:10],
                    entry.domain,
                    entry.language,
                    f"{entry.score:.2f}",
                    date,
                    prompt_text,
                )

            self.console.print(table)

            if len(history_results) > 20:
                self.console.print(
                    f"[dim]... and {len(history_results) - 20} more results[/dim]"
                )

        # Display favorites results
        if favorites_results:
            self.console.print("\n[bold magenta]Favorites Results:[/bold magenta]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim", width=12)
            table.add_column("Domain", width=12)
            table.add_column("Tags", width=20)
            table.add_column("Score", width=6)
            table.add_column("Date", width=10)
            table.add_column("Prompt", width=50 if not show_full_text else None)

            for entry in favorites_results[:20]:  # Limit display to 20
                date = datetime.fromisoformat(entry.timestamp).strftime("%Y-%m-%d")
                prompt_text = (
                    entry.prompt_text
                    if show_full_text
                    else entry.prompt_text[:47] + "..."
                    if len(entry.prompt_text) > 50
                    else entry.prompt_text
                )
                tags_str = ", ".join(entry.tags[:3])
                if len(entry.tags) > 3:
                    tags_str += f" +{len(entry.tags) - 3}"

                table.add_row(
                    entry.id[:10],
                    entry.domain,
                    tags_str,
                    f"{entry.score:.2f}",
                    date,
                    prompt_text,
                )

            self.console.print(table)

            if len(favorites_results) > 20:
                self.console.print(
                    f"[dim]... and {len(favorites_results) - 20} more results[/dim]"
                )


# Singleton instance
_advanced_search_instance = None


def get_advanced_search() -> AdvancedSearch:
    """Get singleton instance of AdvancedSearch.

    Returns:
        AdvancedSearch instance
    """
    global _advanced_search_instance
    if _advanced_search_instance is None:
        _advanced_search_instance = AdvancedSearch()
    return _advanced_search_instance
