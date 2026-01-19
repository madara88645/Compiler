import typer
from pathlib import Path
from typing import Optional
import yaml
from rich.console import Console
from app.optimizer.models import OptimizationConfig
from app.optimizer.judge import JudgeAgent
from app.optimizer.mutator import MutatorAgent
from app.optimizer.evolution import EvolutionEngine
from app.testing.models import TestSuite
from app.llm.factory import get_provider

app = typer.Typer(help="Evolutionary Prompt Optimization")
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
):
    """
    Optimize a prompt using evolutionary algorithms and test feedback.
    """

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
    config = OptimizationConfig(max_generations=generations, target_score=target_score)

    # Initialize Agents with provider
    console.print("[bold cyan]Initializing Optimization Agents...[/bold cyan]")
    judge = JudgeAgent(provider=llm_provider)
    mutator = MutatorAgent(config, provider=llm_provider)
    engine = EvolutionEngine(config, judge, mutator)

    # Run Loop
    console.print(
        f"[bold green]Starting Optimization Loop[/bold green] (Gen: {generations}, Target: {target_score})"
    )
    best = engine.run(initial_prompt, suite, base_dir=suite_file.parent)

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
