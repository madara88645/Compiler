import typer
from pathlib import Path
from typing import Optional
import yaml
from rich.console import Console
from rich.panel import Panel
from app.optimizer.models import OptimizationConfig
from app.optimizer.judge import JudgeAgent
from app.optimizer.mutator import MutatorAgent
from app.optimizer.evolution import EvolutionEngine
from app.testing.models import TestSuite
from app.llm.factory import get_provider
from app.reporting import ReportGenerator
from app.optimizer.estimator import estimate_run_cost
import webbrowser


app = typer.Typer(help="Evolutionary Prompt Optimization")
history_app = typer.Typer(help="Manage optimization history")
app.add_typer(history_app, name="history")

console = Console()


@app.command("run")
def optimize_run(
    prompt_file: Path = typer.Argument(..., help="Path to initial prompt file"),
    suite_file: Path = typer.Argument(..., help="Path to test suite YAML"),
    generations: int = typer.Option(3, "--generations", "-g", help="Max generations"),
    target_score: float = typer.Option(1.0, "--target", "-t", help="Target score (0.0-1.0)"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Save best prompt to file"),
    provider: str = typer.Option(
        "mock", "--provider", "-p", help="LLM provider: openai, ollama, or mock"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model identifier (e.g., gpt-4o, llama3)"
    ),
    interactive_every: int = typer.Option(
        0, "--interactive-every", "-i", help="Pause every N generations for human input (0 = never)"
    ),
    budget: Optional[float] = typer.Option(None, "--budget", "-b", help="Max budget in USD"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Estimate cost and exit"),
):
    """
    Optimize a prompt using evolutionary algorithms and test feedback.
    """
    from app.optimizer.callbacks import InteractiveCallback

    if not prompt_file.exists():
        console.print(f"[red]Prompt file not found: {prompt_file}[/red]")
        raise typer.Exit(1)

    if not suite_file.exists():
        console.print(f"[red]Suite file not found: {suite_file}[/red]")
        raise typer.Exit(1)

    # Load Inputs
    initial_prompt = prompt_file.read_text(encoding="utf-8")
    try:
        suite_data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
        suite = TestSuite(**suite_data)
    except Exception as e:
        console.print(f"[red]Error parsing suite:[/red] {e}")
        raise typer.Exit(1)

    # Initialize LLM Provider
    llm_provider = None
    if provider.lower() != "mock":
        try:
            llm_provider = get_provider(provider, model)
            console.print(f"[cyan]Using LLM provider:[/cyan] {provider} ({model or 'default'})")
        except Exception as e:
            console.print(f"[yellow]Failed to initialize provider '{provider}': {e}[/yellow]")
            console.print("[yellow]Falling back to mock provider[/yellow]")
    else:
        console.print("[dim]Using mock provider (no LLM calls)[/dim]")

    # Config
    config = OptimizationConfig(
        max_generations=generations,
        target_score=target_score,
        interactive_every=interactive_every,
        budget_limit=budget,
    )

    if dry_run:
        console.print("[bold cyan]Running Cost Estimation...[/bold cyan]")
        estimate = estimate_run_cost(config, initial_prompt)
        console.print(Panel(estimate["message"], title="💰 Dry Run Estimate", border_style="green"))
        return

    # Initialize Callback
    callback = InteractiveCallback(interactive_every=interactive_every)
    if interactive_every > 0:
        console.print(
            f"[yellow]Interactive mode: Pausing every {interactive_every} generation(s)[/yellow]"
        )

    # Initialize Agents with provider
    console.print("[bold cyan]Initializing Optimization Agents...[/bold cyan]")
    judge = JudgeAgent(provider=llm_provider)
    mutator = MutatorAgent(config, provider=llm_provider)
    engine = EvolutionEngine(config, judge, mutator)

    # Run Loop with callback
    console.print(
        f"[bold green]Starting Optimization Loop[/bold green] (Gen: {generations}, Target: {target_score})"
    )
    opt_run = engine.run(initial_prompt, suite, base_dir=suite_file.parent, callback=callback)
    best = opt_run.best_candidate

    # Generate Report
    report_path = Path.home() / ".promptc" / "reports" / f"report_{opt_run.id}.html"
    try:
        ReportGenerator().generate_report(opt_run, report_path)
        console.print(f"📊 Detailed Report generated at: [blue]{report_path}[/blue]")
        webbrowser.open(report_path.as_uri())
    except Exception as e:
        console.print(f"[red]Failed to generate report:[/red] {e}")

    # Report Results
    console.print("\n[bold cyan]Optimization Complete![/bold cyan]")
    console.print(f"Best Score: [green]{best.score:.2f}[/green]")
    console.print(f"Generation: {best.generation}")
    console.print(f"Type: {best.mutation_type}")

    if best.result and best.result.failures:
        console.print(f"[yellow]Remaining Failures: {best.result.failed_count}[/yellow]")

    if out:
        out.write_text(best.prompt_text, encoding="utf-8")
        console.print(f"Saved best prompt to: {out}")
    else:
        console.print("\n[bold]Best Prompt Content:[/bold]")
        console.print(best.prompt_text)


@app.command("resume")
def optimize_resume(
    run_id: str = typer.Argument(..., help="ID (or prefix) of the run to resume"),
    suite_file: Path = typer.Option(..., "--suite", "-s", help="Path to test suite YAML"),
    generations: int = typer.Option(3, "--generations", "-g", help="Additional generations to run"),
    target_score: float = typer.Option(1.0, "--target", "-t", help="Target score (0.0-1.0)"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Save best prompt to file"),
    provider: str = typer.Option(
        "mock", "--provider", "-p", help="LLM provider: openai, ollama, or mock"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model identifier (e.g., gpt-4o, llama3)"
    ),
):
    """
    Resume an existing optimization run.
    """
    from app.optimizer.history import HistoryManager

    if not suite_file.exists():
        console.print(f"[red]Suite file not found: {suite_file}[/red]")
        raise typer.Exit(1)

    # Load Suite
    try:
        suite_data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
        suite = TestSuite(**suite_data)
    except Exception as e:
        console.print(f"[red]Error parsing suite:[/red] {e}")
        raise typer.Exit(1)

    # Resolve Run ID
    manager = HistoryManager()

    # Simple prefix matching logic
    target_run_id = run_id
    if not manager.load_run(run_id):
        runs = manager.list_runs()
        matches = [r for r in runs if r["id"].startswith(run_id)]
        if len(matches) == 1:
            target_run_id = matches[0]["id"]
        elif len(matches) > 1:
            console.print(
                f"[red]Ambiguous ID '{run_id}'. Matches: {', '.join(m['id'][:8] for m in matches)}[/red]"
            )
            raise typer.Exit(1)
        else:
            console.print(f"[red]Run not found: {run_id}[/red]")
            raise typer.Exit(1)

    # Load the run just to get config for initialization?
    # Actually EvolutionEngine.resume_from loads it.
    # But we need to initialize Agents first.
    # The config passed to Mutator/Engine init will be overwritten by resume_from (mostly),
    # except Mutator uses it. We should probably load it here.

    run = manager.load_run(target_run_id)
    if not run:
        console.print(f"[red]Failed to load run: {target_run_id}[/red]")
        raise typer.Exit(1)

    # Initialize LLM Provider (Allow override)
    llm_provider = None
    if provider.lower() != "mock":
        try:
            llm_provider = get_provider(provider, model)
            console.print(f"[cyan]Using LLM provider:[/cyan] {provider} ({model or 'default'})")
        except Exception as e:
            console.print(f"[yellow]Failed to initialize provider '{provider}': {e}[/yellow]")
            console.print("[yellow]Falling back to mock provider[/yellow]")
    else:
        console.print("[dim]Using mock provider (no LLM calls)[/dim]")

    # Initialize Agents
    # Note: run.config might be stale if we assume we can upgrade config params (like model).
    updated_config = run.config
    updated_config.target_score = target_score  # Allow target update

    console.print(f"[bold cyan]Resuming Run {target_run_id}...[/bold cyan]")
    judge = JudgeAgent(provider=llm_provider)
    mutator = MutatorAgent(updated_config, provider=llm_provider)
    engine = EvolutionEngine(updated_config, judge, mutator)

    # Resume Loop
    opt_run = engine.resume_from(
        target_run_id, suite, base_dir=suite_file.parent, extra_generations=generations
    )
    best = opt_run.best_candidate

    # Generate Report
    report_path = Path.home() / ".promptc" / "reports" / f"report_{opt_run.id}.html"
    try:
        ReportGenerator().generate_report(opt_run, report_path)
        console.print(f"📊 Detailed Report generated at: [blue]{report_path}[/blue]")
        webbrowser.open(report_path.as_uri())
    except Exception as e:
        console.print(f"[red]Failed to generate report:[/red] {e}")

    # Report Results
    console.print("\n[bold cyan]Optimization Complete![/bold cyan]")
    console.print(f"Best Score: [green]{best.score:.2f}[/green]")
    console.print(f"Generation: {best.generation}")
    console.print(f"Type: {best.mutation_type}")

    if best.result and best.result.failures:
        console.print(f"[yellow]Remaining Failures: {best.result.failed_count}[/yellow]")

    if out:
        out.write_text(best.prompt_text, encoding="utf-8")
        console.print(f"Saved best prompt to: {out}")
    else:
        console.print("\n[bold]Best Prompt Content:[/bold]")
        console.print(best.prompt_text)


def history_list(limit: int = typer.Option(10, "--limit", "-l", help="Number of runs to show")):
    """List past optimization runs."""
    from app.optimizer.history import HistoryManager
    from rich.table import Table

    manager = HistoryManager()
    runs = manager.list_runs()

    if not runs:
        console.print("[yellow]No history found.[/yellow]")
        return

    table = Table(title="Optimization History")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Model", style="magenta")
    table.add_column("Gens", justify="right")

    for run in runs[:limit]:
        table.add_row(
            run["id"][:8],
            run["date"],
            f"{run['best_score']:.2f}",
            run["model"],
            str(run["generations"]),
        )

    console.print(table)


@history_app.command("show")
def history_show(run_id: str):
    """Show details of a specific run."""
    from app.optimizer.history import HistoryManager

    manager = HistoryManager()

    # Try exact match first
    run = manager.load_run(run_id)
    if not run:
        # Try prefix search
        runs = manager.list_runs()
        matches = [r for r in runs if r["id"].startswith(run_id)]
        if len(matches) == 1:
            run = manager.load_run(matches[0]["id"])
        elif len(matches) > 1:
            console.print(
                f"[red]Ambiguous ID '{run_id}'. Matches: {', '.join(m['id'][:8] for m in matches)}[/red]"
            )
            raise typer.Exit(1)

    if not run:
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Run Details: {run.id}[/bold cyan]")
    console.print(
        f"Date: [green]{run.id}[/green] (TODO: Fix date in model)"
    )  # Model doesn't have date yet, relying on ID/file
    console.print(f"Target Score: {run.config.target_score}")
    console.print(f"Generations: {len(run.generations)}")

    if run.best_candidate:
        console.print(f"\n[bold]Best Candidate (Score: {run.best_candidate.score:.2f})[/bold]")
        console.print(f"Type: {run.best_candidate.mutation_type}")
        console.print("-" * 20)
        console.print(run.best_candidate.prompt_text)
        console.print("-" * 20)
