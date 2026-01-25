from __future__ import annotations
from typing import Protocol, Optional, Union, Dict, Any
from .models import Candidate, EvaluationResult


class EvolutionCallback(Protocol):
    """Protocol for receiving events from the EvolutionEngine."""

    def on_start(self, initial_prompt: str, target_score: float) -> None:
        """Called when optimization starts."""
        ...

    def on_generation_start(self, generation: int) -> None:
        """Called when a new generation begins."""
        ...

    def on_candidate_evaluated(self, candidate: Candidate, result: EvaluationResult) -> None:
        """Called after a candidate is scored."""
        ...

    def on_new_best(self, candidate: Candidate, score: float) -> None:
        """Called when a new global best score is found."""
        ...

    def on_complete(self, best_candidate: Candidate) -> None:
        """Called when optimization finishes."""
        ...

    def on_human_intervention_needed(
        self, current_best: Candidate, generation: int
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Called when human intervention is requested.

        Args:
            current_best: The current best candidate.
            generation: The current generation number.

        Returns:
            - None: Continue without changes.
            - str: A new prompt string (legacy support).
            - dict: Structured instruction, e.g.:
                {"type": "feedback", "content": "Make it shorter"}
                {"type": "edit", "content": "New prompt text..."}
        """
        ...


class InteractiveCallback:
    """
    Interactive callback implementation for Human-in-the-Loop optimization.
    Prompts the user for input at specified generation intervals.
    """

    def __init__(self, interactive_every: int = 0):
        """
        Args:
            interactive_every: Pause every N generations for human input. 0 = never.
        """
        self.interactive_every = interactive_every
        self._generation_count = 0

    def on_start(self, initial_prompt: str, target_score: float) -> None:
        pass

    def on_generation_start(self, generation: int) -> None:
        self._generation_count = generation

    def on_candidate_evaluated(self, candidate: Candidate, result: EvaluationResult) -> None:
        pass

    def on_new_best(self, candidate: Candidate, score: float) -> None:
        pass

    def on_complete(self, best_candidate: Candidate) -> None:
        pass

    def on_human_intervention_needed(
        self, current_best: Candidate, generation: int
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """
        Pause and prompt the user for modifications.
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt

        console = Console()

        # Clear header
        console.print()
        console.print(f"[bold yellow]⏸️  Evolution Paused at Gen {generation}[/bold yellow]")
        console.print(f"[cyan]Current Best Score:[/cyan] [green]{current_best.score:.2f}[/green]")
        console.print()

        # Show current prompt
        console.print(
            Panel(
                current_best.prompt_text,
                title="[bold]Current Best Prompt[/bold]",
                border_style="cyan",
            )
        )
        console.print()

        # Menu
        console.print("[bold]Options:[/bold]")
        console.print("[1] Continue (No change)")
        console.print("[2] Give Feedback (Steer with words)")
        console.print("[3] Manual Edit (Rewrite code)")
        console.print()

        choice = Prompt.ask("Select an option", choices=["1", "2", "3"], default="1")

        if choice == "1":
            console.print("[dim]Continuing evolution...[/dim]")
            return None

        elif choice == "2":
            # Steering
            feedback = Prompt.ask("[bold yellow]Enter your instructions/feedback[/bold yellow]")
            if not feedback.strip():
                console.print("[dim]Empty feedback. Continuing...[/dim]")
                return None
            return {"type": "feedback", "content": feedback.strip()}

        elif choice == "3":
            # Manual Edit
            console.print()
            console.print("[bold yellow]Enter your modified prompt below.[/bold yellow]")

            console.print(
                "[dim]Type 'END' on a line by itself to finish, or 'CANCEL' to abort.[/dim]"
            )

            current_lines = []
            try:
                while True:
                    line = input()
                    if line.strip().upper() == "END":
                        break
                    if line.strip().upper() == "CANCEL":
                        console.print("[dim]Modification cancelled.[/dim]")
                        return None
                    current_lines.append(line)
            except EOFError:
                pass

            new_prompt = "\n".join(current_lines)

            if not new_prompt.strip():
                console.print("[dim]Empty input. Continuing...[/dim]")
                return None

            # Validate
            from app.optimizer.utils import validate_human_input

            if validate_human_input(current_best.prompt_text, new_prompt):
                console.print(
                    Panel(
                        new_prompt,
                        title="[bold green]✓ New Prompt Accepted[/bold green]",
                        border_style="green",
                    )
                )
                return {"type": "edit", "content": new_prompt}
            else:
                console.print("[bold red]❌ Validation Failed: Missing variables.[/bold red]")
                console.print("[dim]Validation failed. Continuing with original...[/dim]")
                return None

        return None

    def should_pause(self, generation: int) -> bool:
        """Check if we should pause for human input at this generation."""
        if self.interactive_every <= 0:
            return False
        return generation > 0 and generation % self.interactive_every == 0
