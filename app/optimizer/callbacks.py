from typing import Protocol, Optional
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
