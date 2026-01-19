from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Tree, Static, Button, Digits, Log
from textual.reactive import reactive
from typing import Optional, List, Dict, Any

class EvolutionTree(Tree):
    """Tree widget showing the lineage of prompt generations."""
    def __init__(self, *args, **kwargs):
        super().__init__("Generations", id="evolution-tree", *args, **kwargs)
        self.root.expand()

class ScorePlot(Static):
    """Widget to visualize score trends (ascii sparkline)."""
    scores: reactive[List[float]] = reactive([])
    
    def watch_scores(self, scores: List[float]) -> None:
        if not scores:
            self.update("No data")
            return
            
        # Simple ASCII plot
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        
        # Draw sparkline
        total_width = self.size.width or 40
        data = scores[-total_width:]
        
        chars = " ▂▃▄▅▆▇█"
        line = ""
        for s in data:
            if max_score == min_score:
                idx = len(chars) - 1
            else:
                idx = int((s - min_score) / (max_score - min_score) * (len(chars) - 1))
            line += chars[idx]
            
        self.update(f"[bold cyan]Score Trend:[/bold cyan] {line}\n[dim]High: {max_score:.2f} | Low: {min_score:.2f}[/dim]")

class OptimizationScreen(Screen):
    """Screen for the Evolutionary Prompt Optimizer."""
    
    CSS = """
    OptimizationScreen {
        layout: grid;
        grid-size: 2;
        grid-columns: 30% 70%;
        grid-rows: 1fr;
    }
    
    #sidebar {
        dock: left;
        width: 30%;
        height: 100%;
        border-right: solid $accent;
    }
    
    #main-content {
        height: 100%;
        padding: 1;
    }
    
    #score-panel {
        height: 5;
        dock: top;
        border-bottom: solid $accent;
        padding: 1;
    }
    
    #log-panel {
        height: 1fr;
        border-top: solid $accent;
    }
    
    .status-badge {
        background: $primary;
        color: white;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back to Search"),
        ("s", "start_optimization", "Start"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Sidebar with Tree
        with Container(id="sidebar"):
            yield Static("[bold]Generations[/bold]", classes="header")
            yield EvolutionTree()
            yield Button("Start Optimization", id="btn-start", variant="success")

        # Main Content
        with Vertical(id="main-content"):
            # Top stats
            with Horizontal(id="score-panel"):
                yield Digits("0.00", id="current-score")
                yield ScorePlot(id="score-plot")
            
            # Detailed View / Log
            yield Log(id="activity-log", highlight=True)
            
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#activity-log").write("[dim]Ready to optimize. Press 's' to start simulation.[/dim]")

    def action_start_optimization(self) -> None:
        """Trigger the start flow."""
        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#activity-log").write("[bold green]Starting optimization...[/bold green]")
        
        # Run in thread
        import threading
        t = threading.Thread(target=self._run_optimization)
        t.start()
        
    def _run_optimization(self) -> None:
        """Background thread for optimization."""
        # Setup (Mock for now, normally would get from args/context)
        from app.optimizer.evolution import EvolutionEngine
        from app.optimizer.mutator import MutatorAgent
        from app.optimizer.judge import JudgeAgent
        from app.optimizer.models import OptimizationConfig
        from app.testing.models import TestSuite, TestCase
        from app.llm.factory import get_provider
        from pathlib import Path
        
        # Config
        config = OptimizationConfig(max_generations=10, target_score=1.0)
        provider = get_provider("mock")
        
        mutator = MutatorAgent(config=config, provider=provider)
        judge = JudgeAgent(provider=provider)
        engine = EvolutionEngine(config, judge, mutator)
        
        # Mock Data
        initial_prompt = "Write a poem about {{topic}}."
        suite = TestSuite(name="Demo", test_cases=[
            TestCase(inputs={"topic": "nature"}, requirements=["must contain 'memory safety'"])
        ])
        
        # Run with self as callback adapter
        callback = TUIEvolutionCallback(self)
        try:
            engine.run(initial_prompt, suite, Path("."), callback=callback)
        except Exception as e:
            self.app.call_from_thread(self._log_error, str(e))
            
    def _log_error(self, msg: str) -> None:
        self.query_one("#activity-log").write(f"[bold red]Error: {msg}[/bold red]")
        self.query_one("#btn-start", Button).disabled = False

from app.optimizer.callbacks import EvolutionCallback
from app.optimizer.models import Candidate, EvaluationResult

class TUIEvolutionCallback:
    """Adapter to push updates to the OptimizationScreen."""
    def __init__(self, screen: OptimizationScreen):
        self.screen = screen
        self.app = screen.app
        
    def on_start(self, initial_prompt: str, target_score: float) -> None:
        self.app.call_from_thread(self._update_log, f"Optimization started. Target: {target_score}")
        
    def on_generation_start(self, generation: int) -> None:
        self.app.call_from_thread(self._update_log, f"Generation {generation} started...")
        
    def on_candidate_evaluated(self, candidate: Candidate, result: EvaluationResult) -> None:
        # Check if we should log failures? Maybe too noisy.
        pass
        
    def on_new_best(self, candidate: Candidate, score: float) -> None:
        self.app.call_from_thread(self._handle_new_best, candidate, score)
        
    def on_complete(self, best_candidate: Candidate) -> None:
        self.app.call_from_thread(self._update_log, f"[bold gold]DONE! Best Score: {best_candidate.score}[/bold gold]")
        self.app.call_from_thread(lambda: setattr(self.screen.query_one("#btn-start", Button), "disabled", False))

    def _update_log(self, msg: str) -> None:
        self.screen.query_one("#activity-log").write(msg)
        
    def _handle_new_best(self, candidate: Candidate, score: float) -> None:
        # Update Score Display
        self.screen.query_one("#current-score", Digits).update(f"{score:.2f}")
        
        # Update Plot
        # optimization screen needs to track scores to update plot
        # For simplicity, we just push the new score to the widget
        plot = self.screen.query_one("#score-plot", ScorePlot)
        new_scores = plot.scores + [score]
        plot.scores = new_scores
        
        # Update Log
        self.screen.query_one("#activity-log").write(f"[cyan]New Best:[/cyan] {score:.2f} ({candidate.mutation_type})")
        
        # Update Tree
        tree = self.screen.query_one("#evolution-tree", Tree)
        # Simplified tree update: just add under root for now
        # in reality we'd want a map of parents
        tree.root.add(f"Gen {candidate.generation}: {candidate.mutation_type} ({score:.2f})")
