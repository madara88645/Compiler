"""Modern Terminal UI for PromptC using Textual."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    Input,
    Button,
    Static,
    ListView,
    ListItem,
    Label,
)
from textual.binding import Binding
from rich.text import Text
from typing import Optional, List

from app.search import get_search_engine, SearchResult, SearchResultType
from app.smart_tags import get_smart_tagger


class SearchResultItem(ListItem):
    """Custom list item for search results."""

    def __init__(self, result: SearchResult, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = result

    def render(self) -> Text:
        """Render the result with icon and score."""
        icons = {
            SearchResultType.HISTORY: "📝",
            SearchResultType.FAVORITE: "⭐",
            SearchResultType.TEMPLATE: "📄",
            SearchResultType.SNIPPET: "📋",
            SearchResultType.COLLECTION: "🗂️",
        }
        icon = icons.get(self.result.result_type, "•")
        score = f"{self.result.score:5.1f}"
        title = self.result.title[:50]

        text = Text()
        text.append(f"{icon} ", style="bold yellow")
        text.append(f"[{score}] ", style="green")
        text.append(title, style="cyan")
        return text


class TagItem(ListItem):
    """Custom list item for tags."""

    def __init__(self, tag: str, count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tag = tag
        self.count = count

    def render(self) -> Text:
        """Render the tag with usage count."""
        text = Text()
        text.append("🏷️  ", style="bold yellow")
        text.append(f"{self.tag:20}", style="cyan")
        text.append(f" [{self.count:3}]", style="green")
        return text


class CategoryItem(ListItem):
    """Custom list item for template categories."""

    def __init__(self, category: str, count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category
        self.count = count

    def render(self) -> Text:
        """Render the category with template count."""
        text = Text()
        text.append("📁 ", style="bold blue")
        text.append(f"{self.category:20}", style="cyan bold")
        text.append(f" ({self.count} templates)", style="green dim")
        return text


class PreviewPane(Static):
    """Preview pane showing detailed information about selected result."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_result: Optional[SearchResult] = None

    def update_preview(self, result: SearchResult):
        """Update preview with result details."""
        self.current_result = result

        # Build rich panel
        content = []

        # Header info
        content.append(f"[bold cyan]Type:[/] {result.result_type.value}")
        content.append(f"[bold green]Score:[/] {result.score:.2f}")
        content.append(f"[bold yellow]ID:[/] {result.id}")
        content.append("")

        # Title
        content.append("[bold white]Title:[/]")
        content.append(result.title)
        content.append("")

        # Content
        content.append("[bold white]Content:[/]")
        content.append(result.content[:500] + ("..." if len(result.content) > 500 else ""))
        content.append("")

        # Metadata
        if result.metadata:
            content.append("[bold white]Metadata:[/]")
            for key, value in list(result.metadata.items())[:5]:
                content.append(f"  {key}: {value}")

        self.update("\n".join(content))


class SearchApp(App):
    """A Textual app for searching PromptC data."""

    CSS = """
    Screen {
        background: $surface;
    }

    #search-container {
        dock: top;
        height: 3;
        background: $primary;
        padding: 0 1;
    }

    #search-input {
        width: 1fr;
        margin-right: 1;
    }

    #search-button {
        width: 12;
    }

    #main-container {
        height: 1fr;
    }

    #results-container {
        width: 50%;
        border: solid $accent;
        height: 1fr;
    }

    #preview-container {
        width: 50%;
        border: solid $accent;
        height: 1fr;
        padding: 1;
    }

    ListView {
        height: 1fr;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: $boost;
    }

    ListItem.-highlighted {
        background: $accent;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-darken-2;
        color: $text;
        content-align: center middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("f1", "search_focus", "Search", show=True),
        Binding("f2", "show_history", "History", show=True),
        Binding("f3", "show_favorites", "Favorites", show=True),
        Binding("f4", "show_collections", "Collections", show=True),
        Binding("f5", "show_tags", "Tags", show=True),
        Binding("f6", "show_stats", "Stats", show=True),
        Binding("f7", "show_categories", "Categories", show=True),
        Binding("f8", "show_advanced_search", "Adv.Search", show=True),
        Binding("escape", "search_focus", "Focus Search", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_engine = get_search_engine()
        self.smart_tagger = get_smart_tagger()
        self.current_results: List[SearchResult] = []
        self.tags_mode = False
        self.categories_mode = False
        self.stats_mode = False
        self.advanced_search_mode = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)

        # Search bar
        with Container(id="search-container"):
            with Horizontal():
                yield Input(placeholder="Search prompts, templates, snippets...", id="search-input")
                yield Button("Search", variant="primary", id="search-button")

        # Main content area
        with Horizontal(id="main-container"):
            # Results list
            with Vertical(id="results-container"):
                yield Label("Results (0)", id="results-label")
                yield ListView(id="results-list")

            # Preview pane
            with ScrollableContainer(id="preview-container"):
                yield PreviewPane(id="preview-pane")

        # Status bar
        yield Static(
            "Ready | Press F1 for Search, F2-F4 for filters, Ctrl+C to quit", id="status-bar"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.title = "PromptC Terminal UI"
        self.sub_title = "Modern Search Interface"

        # Initial stats load
        stats = self.search_engine.get_stats()
        total = stats.get("total", 0)
        self.query_one("#status-bar", Static).update(
            f"Ready | {total} searchable items | Press F1-F4 for actions"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission."""
        if event.input.id == "search-input":
            self.perform_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "search-button":
            self.perform_search()

    def perform_search(self, query: Optional[str] = None, types_filter: Optional[List[str]] = None):
        """Perform search and update results."""
        if query is None:
            search_input = self.query_one("#search-input", Input)
            query = search_input.value.strip()

        if not query:
            self.query_one("#status-bar", Static).update("⚠️ Please enter a search query")
            return

        # Update status
        self.query_one("#status-bar", Static).update(f"🔍 Searching for '{query}'...")

        # Perform search
        result_types = None
        if types_filter:
            result_types = [SearchResultType(t) for t in types_filter]

        results = self.search_engine.search(query, result_types=result_types, limit=50)
        self.current_results = results

        # Update results list
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        for result in results:
            results_list.append(SearchResultItem(result))

        # Update label
        self.query_one("#results-label", Label).update(f"Results ({len(results)})")

        # Update status
        self.query_one("#status-bar", Static).update(
            f"✅ Found {len(results)} results for '{query}'"
        )

        # Focus on results
        if results:
            results_list.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle result selection."""
        if event.list_view.id == "results-list":
            if isinstance(event.item, SearchResultItem):
                result = event.item.result
                preview_pane = self.query_one("#preview-pane", PreviewPane)
                preview_pane.update_preview(result)
            elif isinstance(event.item, CategoryItem):
                # Show templates in selected category
                self._show_category_templates(event.item.category)

    def action_search_focus(self) -> None:
        """Focus on search input."""
        self.query_one("#search-input", Input).focus()

    def action_show_history(self) -> None:
        """Show only history items."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip() or "*"
        self.perform_search(query, types_filter=["history"])
        self.query_one("#status-bar", Static).update("📝 Filtering: History only")

    def action_show_favorites(self) -> None:
        """Show only favorites."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip() or "*"
        self.perform_search(query, types_filter=["favorite"])
        self.query_one("#status-bar", Static).update("⭐ Filtering: Favorites only")

    def action_show_collections(self) -> None:
        """Show only collections."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip() or "*"
        self.perform_search(query, types_filter=["collection"])
        self.query_one("#status-bar", Static).update("🗂️ Filtering: Collections only")

    def action_show_tags(self) -> None:
        """Show tags panel."""
        if self.tags_mode:
            # Switch back to search mode
            self.tags_mode = False
            self.query_one("#results-label", Label).update("Results (0)")
            self.query_one("#status-bar", Static).update("Ready | Press F1-F5 for actions")
            results_list = self.query_one("#results-list", ListView)
            results_list.clear()
            return

        # Switch to tags mode
        self.tags_mode = True
        self.query_one("#status-bar", Static).update("🏷️ Tags Panel | Loading tags...")

        # Get tag statistics
        tag_stats = self.smart_tagger.get_tag_statistics()

        # Update results list with tags
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        for tag, count in tag_stats:
            results_list.append(TagItem(tag, count))

        # Update label
        self.query_one("#results-label", Label).update(f"Tags ({len(tag_stats)})")

        # Update status
        total_uses = sum(count for _, count in tag_stats)
        self.query_one("#status-bar", Static).update(
            f"🏷️ {len(tag_stats)} unique tags, {total_uses} total uses | Press F5 again to exit"
        )

        # Update preview with tag stats
        preview_pane = self.query_one("#preview-pane", PreviewPane)
        content = [
            "[bold cyan]Tag Analytics[/]",
            "",
            f"[bold white]Total Unique Tags:[/] [yellow]{len(tag_stats)}[/]",
            f"[bold white]Total Tag Uses:[/] [green]{total_uses}[/]",
            "",
            "[bold white]Top 10 Tags:[/]",
        ]

        for i, (tag, count) in enumerate(tag_stats[:10], 1):
            bar = "█" * min(count, 30)
            content.append(f"{i:2}. [cyan]{tag:20}[/] [{count:3}] [yellow]{bar}[/]")

        preview_pane.update("\n".join(content))

        # Focus on tags list
        if tag_stats:
            results_list.focus()

    def action_show_categories(self) -> None:
        """Show template categories browser."""
        if self.categories_mode:
            # Switch back to search mode
            self.categories_mode = False
            self.query_one("#results-label", Label).update("Results (0)")
            self.query_one("#status-bar", Static).update("Ready | Press F1-F7 for actions")
            results_list = self.query_one("#results-list", ListView)
            results_list.clear()
            return

        # Switch to categories mode
        self.categories_mode = True
        self.query_one("#status-bar", Static).update(
            "📁 Categories Browser | Loading categories..."
        )

        # Get template categories
        from app.templates_manager import get_templates_manager

        templates_mgr = get_templates_manager()
        all_templates = templates_mgr.get_all()

        # Count templates per category
        category_counts = {}
        for template in all_templates:
            category = template.category or "uncategorized"
            category_counts[category] = category_counts.get(category, 0) + 1

        # Sort by count (descending)
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

        # Update results list with categories
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        for category, count in sorted_categories:
            results_list.append(CategoryItem(category, count))

        # Update label
        self.query_one("#results-label", Label).update(f"Categories ({len(sorted_categories)})")

        # Update status
        total_templates = sum(count for _, count in sorted_categories)
        self.query_one("#status-bar", Static).update(
            f"📁 {len(sorted_categories)} categories, {total_templates} templates | Press F7 again to exit"
        )

        # Update preview with category tree
        preview_pane = self.query_one("#preview-pane", PreviewPane)
        content = [
            "[bold cyan]Template Categories Overview[/]",
            "",
            f"[bold white]Total Categories:[/] [yellow]{len(sorted_categories)}[/]",
            f"[bold white]Total Templates:[/] [green]{total_templates}[/]",
            "",
            "[bold white]Category Tree:[/]",
            "",
        ]

        for category, count in sorted_categories:
            percentage = (count / total_templates * 100) if total_templates > 0 else 0
            bar_length = int(percentage / 3)  # Scale to fit
            bar = "█" * bar_length
            content.append(
                f"📁 [cyan bold]{category:20}[/] [{count:3}] [yellow]{bar}[/] [dim]{percentage:.1f}%[/dim]"
            )

        preview_pane.update("\n".join(content))

        # Focus on categories list
        if sorted_categories:
            results_list.focus()

    def _show_category_templates(self, category: str) -> None:
        """Show templates in a specific category in preview pane."""
        from app.templates_manager import get_templates_manager

        templates_mgr = get_templates_manager()
        all_templates = templates_mgr.get_all()

        # Filter templates by category
        category_templates = [
            t for t in all_templates if (t.category or "uncategorized") == category
        ]

        # Sort by name
        category_templates.sort(key=lambda t: t.name)

        # Build preview content
        preview_pane = self.query_one("#preview-pane", PreviewPane)
        content = [
            f"[bold cyan]Category: {category}[/]",
            "",
            f"[bold white]Templates:[/] [yellow]{len(category_templates)}[/]",
            "",
        ]

        if category_templates:
            content.append("[bold white]Template List:[/]")
            content.append("")
            for i, template in enumerate(category_templates, 1):
                # Truncate description
                desc = (
                    template.description[:60] + "..."
                    if len(template.description) > 60
                    else template.description
                )
                content.append(f"{i:2}. [cyan bold]{template.name}[/]")
                content.append(f"    [dim]{desc}[/dim]")
                content.append(f"    [yellow]ID:[/] {template.id}")
                if template.tags:
                    tags_str = ", ".join(template.tags[:3])
                    content.append(f"    [green]Tags:[/] {tags_str}")
                content.append("")
        else:
            content.append("[dim]No templates in this category[/dim]")

        preview_pane.update("\n".join(content))

    def action_show_stats(self) -> None:
        """Show statistics dashboard."""
        if self.stats_mode:
            # Switch back to search mode
            self.stats_mode = False
            self.query_one("#results-label", Label).update("Results (0)")
            self.query_one("#status-bar", Static).update("Ready | Press F1-F7 for actions")
            results_list = self.query_one("#results-list", ListView)
            results_list.clear()
            return

        # Switch to stats mode
        self.stats_mode = True
        self.query_one("#status-bar", Static).update("📊 Statistics Dashboard | Loading stats...")

        # Get statistics
        from app.stats_dashboard import get_stats_calculator

        stats_calc = get_stats_calculator()

        # Overall stats
        overall = stats_calc.get_overall_stats()
        recent_7d = stats_calc.get_recent_activity(days=7)
        recent_30d = stats_calc.get_recent_activity(days=30)
        quality = stats_calc.get_quality_metrics()

        # Top items
        top_domains = stats_calc.get_top_domains(5)
        top_tags = stats_calc.get_top_tags(5)
        top_templates = stats_calc.get_top_templates(3)

        # Update results list - show key metrics as list items
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        # Add metric items (using Static as simple display)

        metrics = [
            f"📊 Total Prompts: {overall['total_prompts']}",
            f"⭐ Favorites: {overall['total_favorites']}",
            f"📄 Templates: {overall['total_templates']}",
            f"📋 Snippets: {overall['total_snippets']}",
            f"🗂️ Collections: {overall['total_collections']}",
            "",
            f"📈 Last 7 Days: {recent_7d['total_activity']} actions",
            f"📈 Last 30 Days: {recent_30d['total_activity']} actions",
            "",
            f"⭐ Avg Quality: {quality['average_score']:.1f}/5.0",
            f"🏆 High Quality: {quality['high_quality_percentage']:.1f}%",
        ]

        for metric in metrics:
            if metric:  # Skip empty strings
                item = ListItem()
                item.add_class("metric-item")
                results_list.append(item)

        # Update label
        self.query_one("#results-label", Label).update("Statistics Overview")

        # Update status
        total_items = (
            overall["total_prompts"]
            + overall["total_favorites"]
            + overall["total_templates"]
            + overall["total_snippets"]
        )
        self.query_one("#status-bar", Static).update(
            f"📊 {total_items} total items | Press F6 again to exit"
        )

        # Build detailed stats for preview pane
        preview_pane = self.query_one("#preview-pane", PreviewPane)
        content = [
            "[bold cyan]📊 Statistics Dashboard[/]",
            "",
            "[bold white]Overall Counts:[/]",
            f"  Prompts:     [yellow]{overall['total_prompts']:4}[/]",
            f"  Favorites:   [yellow]{overall['total_favorites']:4}[/]",
            f"  Templates:   [yellow]{overall['total_templates']:4}[/]",
            f"  Snippets:    [yellow]{overall['total_snippets']:4}[/]",
            f"  Collections: [yellow]{overall['total_collections']:4}[/]",
            "",
            "[bold white]Recent Activity:[/]",
            f"  Last 7 days:  [green]{recent_7d['total_activity']:3}[/] actions",
            f"  Last 30 days: [green]{recent_30d['total_activity']:3}[/] actions",
            "",
            "[bold white]Quality Metrics:[/]",
            f"  Average Score: [yellow]{quality['average_score']:.2f}[/]/5.0",
            f"  High Quality:  [green]{quality['high_quality_percentage']:.1f}%[/]",
            f"  Total Rated:   [cyan]{quality['total_rated']}[/]",
            "",
        ]

        # Top domains
        if top_domains:
            content.append("[bold white]Top Domains:[/]")
            for i, domain_info in enumerate(top_domains, 1):
                count = domain_info["count"]
                bar = "█" * min(count, 20)
                content.append(
                    f"  {i}. [cyan]{domain_info['domain']:15}[/] [{count:3}] [yellow]{bar}[/]"
                )
            content.append("")

        # Top tags
        if top_tags:
            content.append("[bold white]Top Tags:[/]")
            for i, tag_info in enumerate(top_tags, 1):
                count = tag_info["count"]
                bar = "█" * min(count // 2, 20)
                content.append(
                    f"  {i}. [green]{tag_info['tag']:15}[/] [{count:3}] [yellow]{bar}[/]"
                )
            content.append("")

        # Top templates
        if top_templates:
            content.append("[bold white]Most Used Templates:[/]")
            for i, tmpl in enumerate(top_templates, 1):
                content.append(
                    f"  {i}. [cyan]{tmpl['name']:25}[/] [dim]({tmpl['use_count']} uses)[/dim]"
                )
            content.append("")

        # Add sparkline for daily trend
        daily_trend = stats_calc.get_daily_activity_trend(days=7)
        if daily_trend:
            sparkline = stats_calc.generate_sparkline(daily_trend, width=30)
            content.append("[bold white]7-Day Activity Trend:[/]")
            content.append(f"  [yellow]{sparkline}[/]")

        preview_pane.update("\n".join(content))

    def action_show_advanced_search(self) -> None:
        """Show advanced search with filters (F8)."""

        self.advanced_search_mode = True
        self.tags_mode = False
        self.categories_mode = False
        self.stats_mode = False

        # Get list view and preview pane
        list_view = self.query_one("#results-list", ListView)
        list_view.clear()
        preview_pane = self.query_one("#preview", PreviewPane)

        # Show advanced search help
        content = [
            "[bold cyan]🔍 Advanced Search[/bold cyan]",
            "",
            "[bold white]Filter Options:[/]",
            "  • Domain filter",
            "  • Language filter",
            "  • Date range (from/to)",
            "  • Tag filter (favorites)",
            "  • Score threshold",
            "  • Result limit",
            "",
            "[bold white]Search Modes:[/]",
            "  • [cyan]Normal[/] - Exact substring match",
            "  • [yellow]Regex[/] - Regular expression patterns",
            "  • [green]Fuzzy[/] - Approximate matching",
            "",
            "[bold white]Search Sources:[/]",
            "  • All (history + favorites)",
            "  • History only",
            "  • Favorites only",
            "",
            "[bold yellow]CLI Examples:[/]",
            "  [dim]promptc search 'machine learning'[/]",
            "  [dim]promptc search --domain coding --language python[/]",
            "  [dim]promptc search 'API.*endpoint' --regex[/]",
            "  [dim]promptc search 'machne lerning' --fuzzy[/]",
            "  [dim]promptc search --from 2025-01-01 --to 2025-12-31[/]",
            "  [dim]promptc search --tags python,api --source favorites[/]",
            "  [dim]promptc search 'test' --min-score 0.8 --limit 10[/]",
            "",
            "[bold green]Quick Search:[/]",
            "Type your query in the search box above and press Enter.",
            "The advanced search engine will automatically search",
            "through all your prompts with intelligent matching.",
            "",
            "[dim]Press F8 again to return to normal mode[/]",
        ]

        preview_pane.update("\n".join(content))

        # Add search instruction item
        search_item = ListItem()
        search_item.update(
            Text.from_markup(
                "[bold cyan]🔍 Advanced Search Active[/]\n"
                "[dim]Use CLI with filters for advanced features[/]"
            )
        )
        list_view.append(search_item)


def run_tui():
    """Run the TUI application."""
    app = SearchApp()
    app.run()


if __name__ == "__main__":
    run_tui()
