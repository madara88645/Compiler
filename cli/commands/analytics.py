from __future__ import annotations
import json
import typer
import time
from typing import List, Optional
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.analytics import AnalyticsManager, create_record_from_ir
from app.history import get_history_manager
from app.compiler import compile_text_v2

analytics_app = typer.Typer(help="Prompt analytics and metrics")
history_app = typer.Typer(help="Prompt history and quick access")

# ============================================================================
# Analytics Commands
# ============================================================================


@analytics_app.command("record")
def analytics_record(
    prompt: Path = typer.Argument(..., help="Path to prompt file"),
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Run validation and include scores"
    ),
    user_level: str = typer.Option(
        "intermediate",
        "--user-level",
        help="Analytics user level: beginner|intermediate|advanced",
    ),
    task_type: str = typer.Option(
        "general",
        "--task-type",
        help="Analytics task type (e.g. general, debugging, teaching)",
    ),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Analytics tag (repeatable), e.g. --tag project:x --tag load:high",
    ),
):
    """
    Record a prompt compilation in analytics database
    """
    console = Console()

    if not prompt.exists():
        typer.secho(f"Error: File not found: {prompt}", fg=typer.colors.RED)
        raise typer.Exit(1)

    prompt_text = prompt.read_text(encoding="utf-8")

    t0 = time.time()
    with console.status("[cyan]Compiling prompt..."):
        ir = compile_text_v2(prompt_text)
    elapsed_ms = int((time.time() - t0) * 1000)

    validation_result = None
    if validate:
        with console.status("[cyan]Validating prompt..."):
            from app.validator import validate_prompt as validator

            validation_result = validator(ir, prompt_text)

    # Create record
    record = create_record_from_ir(
        prompt_text,
        ir.model_dump(),
        validation_result,
        interface_type="cli",
        user_level=(user_level or "intermediate").strip(),
        task_type=(task_type or "general").strip(),
        time_ms=elapsed_ms,
        iteration_count=1,
        tags=tags or [],
    )

    # Save to analytics
    manager = AnalyticsManager()
    record_id = manager.record_prompt(record)

    console.print(
        Panel(
            f"[green]✓ Recorded successfully[/green]\n\n"
            f"Record ID: [cyan]{record_id}[/cyan]\n"
            f"Score: [yellow]{record.validation_score:.1f}[/yellow]\n"
            f"Domain: {record.domain}\n"
            f"Language: {record.language}\n"
            f"Issues: {record.issues_count}",
            title="[bold]Analytics Record[/bold]",
            border_style="green",
        )
    )


@analytics_app.command("summary")
def analytics_summary(
    days: int = typer.Option(30, help="Number of days to analyze"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    user_level: Optional[str] = typer.Option(None, "--user-level", help="Filter by user level"),
    task_type: Optional[str] = typer.Option(None, "--task-type", help="Filter by task type"),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Filter by tag (repeatable; record must contain all tags)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show analytics summary for a time period
    """
    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing data..."):
        summary = manager.get_summary(
            days=days,
            domain=domain,
            persona=persona,
            user_level=user_level,
            task_type=task_type,
            tags=tags,
        )

    if json_output:
        from dataclasses import asdict

        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
        return

    # Display rich formatted summary
    console.print(f"\n[bold cyan]Analytics Summary[/bold cyan] [dim](Last {days} days)[/dim]\n")

    # Overview table
    overview = Table(show_header=False, box=None, padding=(0, 2))
    overview.add_column("Metric", style="bold")
    overview.add_column("Value")

    overview.add_row("Total Prompts", str(summary.total_prompts))
    overview.add_row(
        "Avg Score", f"[yellow]{summary.avg_score:.1f}[/yellow] ± {summary.score_std:.1f}"
    )
    overview.add_row("Score Range", f"{summary.min_score:.1f} → {summary.max_score:.1f}")
    overview.add_row("Avg Issues", f"{summary.avg_issues:.1f}")
    overview.add_row("Avg Length", f"{summary.avg_prompt_length} chars")

    if summary.improvement_rate != 0:
        color = "green" if summary.improvement_rate > 0 else "red"
        arrow = "↑" if summary.improvement_rate > 0 else "↓"
        overview.add_row(
            "Improvement", f"[{color}]{arrow} {abs(summary.improvement_rate):.1f}%[/{color}]"
        )

    console.print(Panel(overview, title="[bold]Overview[/bold]", border_style="cyan"))

    # Top domains
    if summary.top_domains:
        console.print("\n[bold]Top Domains:[/bold]")
        domains_table = Table(show_header=True, box=None, padding=(0, 2))
        domains_table.add_column("Domain", style="cyan")
        domains_table.add_column("Count", justify="right")
        for domain, count in summary.top_domains:
            domains_table.add_row(domain, str(count))
        console.print(domains_table)

        if summary.most_improved_domain:
            console.print(f"  [green]Most Improved:[/green] {summary.most_improved_domain}")

    # Top personas
    if summary.top_personas:
        console.print("\n[bold]Top Personas:[/bold]")
        personas_table = Table(show_header=True, box=None, padding=(0, 2))
        personas_table.add_column("Persona", style="magenta")
        personas_table.add_column("Count", justify="right")
        for persona, count in summary.top_personas:
            personas_table.add_row(persona, str(count))
        console.print(personas_table)

    # Language distribution
    if summary.language_distribution:
        console.print("\n[bold]Languages:[/bold]")
        for lang, count in summary.language_distribution.items():
            console.print(f"  {lang}: {count}")

    # Top intents
    if summary.top_intents:
        console.print("\n[bold]Top Intents:[/bold]")
        intents_table = Table(show_header=True, box=None, padding=(0, 2))
        intents_table.add_column("Intent", style="yellow")
        intents_table.add_column("Count", justify="right")
        for intent, count in summary.top_intents[:5]:
            intents_table.add_row(intent, str(count))
        console.print(intents_table)


@analytics_app.command("trends")
def analytics_trends(
    days: int = typer.Option(30, help="Number of days to analyze"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    user_level: Optional[str] = typer.Option(None, "--user-level", help="Filter by user level"),
    task_type: Optional[str] = typer.Option(None, "--task-type", help="Filter by task type"),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Filter by tag (repeatable; record must contain all tags)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show score trends over time
    """
    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing trends..."):
        trends = manager.get_score_trends(
            days=days,
            domain=domain,
            persona=persona,
            user_level=user_level,
            task_type=task_type,
            tags=tags,
        )

    if not trends:
        console.print("[yellow]No data available for the specified period[/yellow]")
        return

    if json_output:
        print(json.dumps(trends, ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Score Trends[/bold cyan] [dim](Last {days} days)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Avg Score", justify="right", style="yellow")
    table.add_column("Range", justify="right")
    table.add_column("Count", justify="right", style="dim")
    table.add_column("Trend", justify="center")

    prev_score = None
    for entry in trends:
        # Trend indicator
        if prev_score is not None:
            diff = entry["avg_score"] - prev_score
            if diff > 0:
                trend = f"[green]↑ +{diff:.1f}[/green]"
            elif diff < 0:
                trend = f"[red]↓ {diff:.1f}[/red]"
            else:
                trend = "[dim]→ 0.0[/dim]"
        else:
            trend = "[dim]—[/dim]"

        table.add_row(
            entry["date"],
            f"{entry['avg_score']:.1f}",
            f"{entry['min_score']:.1f}–{entry['max_score']:.1f}",
            str(entry["count"]),
            trend,
        )

        prev_score = entry["avg_score"]

    console.print(table)


@analytics_app.command("domains")
def analytics_domains(
    days: int = typer.Option(30, help="Number of days to analyze"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    user_level: Optional[str] = typer.Option(None, "--user-level", help="Filter by user level"),
    task_type: Optional[str] = typer.Option(None, "--task-type", help="Filter by task type"),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Filter by tag (repeatable; record must contain all tags)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Show domain breakdown and statistics
    """
    console = Console()

    manager = AnalyticsManager()

    with console.status("[cyan]Analyzing domains..."):
        domain_stats = manager.get_domain_breakdown(
            days=days,
            persona=persona,
            user_level=user_level,
            task_type=task_type,
            tags=tags,
        )

    if not domain_stats:
        console.print("[yellow]No data available[/yellow]")
        return

    if json_output:
        print(json.dumps(domain_stats, ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Domain Breakdown[/bold cyan] [dim](Last {days} days)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("Domain", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Avg Score", justify="right", style="yellow")
    table.add_column("Score Range", justify="right")
    table.add_column("Avg Issues", justify="right", style="red")

    # Sort by count
    sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    for domain, stats in sorted_domains:
        table.add_row(
            domain,
            str(stats["count"]),
            f"{stats['avg_score']:.1f}",
            f"{stats['min_score']:.1f}–{stats['max_score']:.1f}",
            f"{stats['avg_issues']:.1f}",
        )

    console.print(table)


@analytics_app.command("list")
def analytics_list(
    limit: int = typer.Option(20, help="Number of records to show"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    persona: Optional[str] = typer.Option(None, help="Filter by persona"),
    user_level: Optional[str] = typer.Option(None, "--user-level", help="Filter by user level"),
    task_type: Optional[str] = typer.Option(None, "--task-type", help="Filter by task type"),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help="Filter by tag (repeatable; record must contain all tags)",
    ),
    min_score: Optional[float] = typer.Option(None, help="Minimum score"),
    max_score: Optional[float] = typer.Option(None, help="Maximum score"),
):
    """
    List recent prompt records
    """
    console = Console()

    manager = AnalyticsManager()

    records = manager.get_records(
        limit=limit,
        domain=domain,
        persona=persona,
        user_level=user_level,
        task_type=task_type,
        tags=tags,
        min_score=min_score,
        max_score=max_score,
    )

    if not records:
        console.print("[yellow]No records found[/yellow]")
        return

    console.print(f"\n[bold cyan]Recent Prompts[/bold cyan] [dim](Last {limit})[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Score", justify="right", style="yellow", width=6)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Language", width=4)
    table.add_column("Issues", justify="right", style="red", width=6)
    table.add_column("Preview", style="dim", width=40)

    for record in records:
        # Format date
        date_str = record.timestamp[:10]  # YYYY-MM-DD

        # Truncate preview
        preview = record.prompt_text.replace("\n", " ")[:50]
        if len(record.prompt_text) > 50:
            preview += "..."

        # Color code score
        score_str = f"{record.validation_score:.1f}"
        if record.validation_score >= 80:
            score_style = "green"
        elif record.validation_score >= 60:
            score_style = "yellow"
        else:
            score_style = "red"

        table.add_row(
            str(record.id),
            date_str,
            f"[{score_style}]{score_str}[/{score_style}]",
            record.domain,
            record.language.upper(),
            str(record.issues_count),
            preview,
        )

    console.print(table)


@analytics_app.command("stats")
def analytics_stats():
    """
    Show overall database statistics
    """
    console = Console()

    manager = AnalyticsManager()
    stats = manager.get_stats()

    info = (
        f"Total Records: [cyan]{stats['total_records']}[/cyan]\n"
        f"Overall Avg Score: [yellow]{stats['overall_avg_score']:.1f}[/yellow]\n"
        f"First Record: [dim]{stats['first_record'] or 'N/A'}[/dim]\n"
        f"Last Record: [dim]{stats['last_record'] or 'N/A'}[/dim]\n"
        f"Database: [dim]{stats['database_path']}[/dim]"
    )

    console.print(
        Panel(
            info, title="[bold cyan]Analytics Database Statistics[/bold cyan]", border_style="cyan"
        )
    )


@analytics_app.command("clean")
def analytics_clean(
    days: int = typer.Option(90, help="Delete records older than N days"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """
    Delete old analytics records
    """
    console = Console()

    if not force:
        confirm = typer.confirm(f"Delete all records older than {days} days?")
        if not confirm:
            typer.echo("Cancelled")
            raise typer.Exit()

    manager = AnalyticsManager()

    with console.status("[cyan]Cleaning old records..."):
        deleted = manager.clear_old_records(days=days)

    console.print(f"[green]✓ Deleted {deleted} old records[/green]")


# ============================================================================
# History Commands
# ============================================================================


@history_app.command("list")
def history_list(
    limit: int = typer.Option(10, help="Number of entries to show"),
    domain: Optional[str] = typer.Option(None, help="Filter by domain"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    List recent prompt history
    """
    console = Console()
    history_mgr = get_history_manager()

    # Get entries
    if domain:
        entries = history_mgr.get_by_domain(domain, limit=limit)
    else:
        entries = history_mgr.get_recent(limit=limit)

    if not entries:
        console.print("[yellow]No history entries found[/yellow]")
        return

    if json_output:
        print(json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2))
        return

    # Display table
    console.print(f"\n[bold cyan]Prompt History[/bold cyan] [dim](Last {limit})[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Score", justify="right", style="yellow", width=6)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Lang", width=4)
    table.add_column("Prompt", style="dim", width=50)

    for entry in entries:
        # Format date
        date_str = entry.timestamp[:10]

        # Truncate prompt
        prompt_preview = entry.prompt_text.replace("\n", " ")[:50]
        if len(entry.prompt_text) > 50:
            prompt_preview += "..."

        # Score color
        if entry.score >= 80:
            score_style = "green"
        elif entry.score >= 60:
            score_style = "yellow"
        else:
            score_style = "red" if entry.score > 0 else "dim"

        score_str = f"{entry.score:.1f}" if entry.score > 0 else "—"

        table.add_row(
            entry.id[:8],
            date_str,
            f"[{score_style}]{score_str}[/{score_style}]",
            entry.domain,
            entry.language.upper(),
            prompt_preview,
        )

    console.print(table)


@history_app.command("search")
def history_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, help="Maximum results"),
):
    """
    Search prompt history
    """
    console = Console()
    history_mgr = get_history_manager()

    entries = history_mgr.search(query, limit=limit)

    if not entries:
        console.print(f"[yellow]No matches found for '{query}'[/yellow]")
        return

    console.print(f"\n[bold cyan]Search Results[/bold cyan] [dim]({len(entries)} matches)[/dim]\n")

    table = Table(show_header=True)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Date", style="cyan", width=10)
    table.add_column("Domain", style="magenta", width=12)
    table.add_column("Prompt", style="white", width=60)

    for entry in entries:
        date_str = entry.timestamp[:10]
        prompt_preview = entry.prompt_text.replace("\n", " ")[:60]
        if len(entry.prompt_text) > 60:
            prompt_preview += "..."

        # Highlight query in preview
        import re

        highlighted = re.sub(
            f"({re.escape(query)})",
            r"[bold yellow]\1[/bold yellow]",
            prompt_preview,
            flags=re.IGNORECASE,
        )

        table.add_row(entry.id[:8], date_str, entry.domain, highlighted)

    console.print(table)


@history_app.command("show")
def history_show(entry_id: str = typer.Argument(..., help="Entry ID")):
    """
    Show full details of a history entry
    """
    console = Console()
    history_mgr = get_history_manager()

    entry = history_mgr.get_by_id(entry_id)

    if not entry:
        console.print(f"[red]Entry '{entry_id}' not found[/red]")
        raise typer.Exit(1)

    # Display details
    console.print(f"\n[bold]Entry {entry.id}[/bold]\n")

    info = (
        f"[cyan]Date:[/cyan] {entry.timestamp}\n"
        f"[cyan]Domain:[/cyan] {entry.domain}\n"
        f"[cyan]Language:[/cyan] {entry.language}\n"
        f"[cyan]IR Version:[/cyan] {entry.ir_version}\n"
    )

    if entry.score > 0:
        score_color = "green" if entry.score >= 80 else "yellow"
        info += f"[cyan]Score:[/cyan] [{score_color}]{entry.score:.1f}[/{score_color}]\n"

    console.print(Panel(info, title="[bold]Info[/bold]", border_style="blue"))

    # Prompt text
    console.print("\n[bold]Prompt:[/bold]")
    console.print(Panel(entry.prompt_text, border_style="green"))


@history_app.command("stats")
def history_stats():
    """
    Show history statistics
    """
    console = Console()
    history_mgr = get_history_manager()

    stats = history_mgr.get_stats()

    if stats["total"] == 0:
        console.print("[yellow]No history entries[/yellow]")
        return
    
    info = (
        f"Total Entries: {stats['total']}\n"
        f"First Entry: {stats.get('first', 'N/A')}\n"
        f"Last Entry: {stats.get('last', 'N/A')}"
    )
    
    console.print(Panel(info, title="[bold cyan]History Stats[/bold cyan]", border_style="cyan"))

    # Domain breakdown if available (simple version)
    # The manager.get_stats() might just return counts.
    # If we want detailed domain breakdown we'd need another method on manager.
