
import typer
import yaml
import time
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.testing.models import TestSuite
from app.testing.runner import TestRunner

app = typer.Typer(help="Prompt Testing Suite")
console = Console()

@app.command("run")
def test_run(
    suite_file: Path = typer.Argument(..., help="Path to test suite YAML"),
    llm: Optional[str] = typer.Option(None, "--llm", help="Override LLM model"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed outputs"),
):
    """Run a test suite against a prompt."""
    if not suite_file.exists():
        console.print(f"[red]Error: Test suite file not found: {suite_file}[/red]")
        raise typer.Exit(1)
        
    # Load Suite
    try:
        data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
        # Validate with Pydantic
        suite = TestSuite(**data)
    except Exception as e:
        console.print(f"[red]Error parsing suite:[/red] {e}")
        raise typer.Exit(1)
        
    console.print(f"[bold blue]Running Suite:[/bold blue] {suite.name}")
    console.print(f"Target Prompt: [cyan]{suite.prompt_file}[/cyan]")
    console.print(f"Cases: {len(suite.test_cases)}")
    
    runner = TestRunner() # Uses Mock by default for now
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Running tests...", total=len(suite.test_cases))
        # Note: run_suite runs all at once, we might want to run individually for progress
        # But for now, let's just run it.
        result = runner.run_suite(suite, base_dir=suite_file.parent)
    
    # Report
    table = Table(title=f"Test Results used {result.total_duration_ms:.2f}ms")
    table.add_column("Case ID", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Duration", justify="right")
    table.add_column("Details")
    
    for res in result.results:
        status_style = "green" if res.passed else "red"
        status_text = "PASS" if res.passed else "FAIL"
        
        details = ""
        if res.failures:
            details = "\n".join([f"- {f}" for f in res.failures])
        elif res.error:
            status_style = "red bold"
            status_text = "ERROR"
            details = str(res.error)
        elif verbose:
            details = f"Output: {res.output[:100]}..."
            
        table.add_row(res.test_case_id, f"[{status_style}]{status_text}[/{status_style}]", f"{res.duration_ms:.2f}ms", details)
        
    console.print(table)
    
    summary_color = "green" if result.failed == 0 and result.errors == 0 else "red"
    console.print(f"[{summary_color}]Passed: {result.passed} | Failed: {result.failed} | Errors: {result.errors}[/{summary_color}]")
    
    if result.failed > 0 or result.errors > 0:
        raise typer.Exit(1)
