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
from textual.message import Message
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
from datetime import datetime
from typing import Optional, List

from app.search import get_search_engine, SearchResult, SearchResultType


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
        content.append(f"[bold white]Title:[/]")
        content.append(result.title)
        content.append("")
        
        # Content
        content.append(f"[bold white]Content:[/]")
        content.append(result.content[:500] + ("..." if len(result.content) > 500 else ""))
        content.append("")
        
        # Metadata
        if result.metadata:
            content.append(f"[bold white]Metadata:[/]")
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
        Binding("escape", "search_focus", "Focus Search", show=False),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_engine = get_search_engine()
        self.current_results: List[SearchResult] = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        
        # Search bar
        with Container(id="search-container"):
            with Horizontal():
                yield Input(
                    placeholder="Search prompts, templates, snippets...",
                    id="search-input"
                )
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
        yield Static("Ready | Press F1 for Search, F2-F4 for filters, Ctrl+C to quit", id="status-bar")
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
        if event.list_view.id == "results-list" and isinstance(event.item, SearchResultItem):
            result = event.item.result
            preview_pane = self.query_one("#preview-pane", PreviewPane)
            preview_pane.update_preview(result)

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


def run_tui():
    """Run the TUI application."""
    app = SearchApp()
    app.run()


if __name__ == "__main__":
    run_tui()
