from __future__ import annotations
from typing import List, Optional
from .models import Candidate, OptimizationConfig
from app.llm.base import LLMProvider
from app.optimizer.strategies import get_strategy
import itertools


class MutatorAgent:
    """
    Agent 3: The Mutator.
    Responsible for generating new prompt variations using dynamic strategies.

    Now delegates to app.optimizer.strategies.
    """

    def __init__(self, config: OptimizationConfig, provider: Optional[LLMProvider] = None):
        self.config = config
        self.provider = provider

    def generate_variations(self, parent: Candidate, failures: List[str]) -> List[Candidate]:
        """
        Calls configured strategies to generate variations.
        """
        candidates = []
        strategies_to_use = self.config.available_strategies

        active_strategies = []
        for name in strategies_to_use:
            try:
                s = get_strategy(name)
                active_strategies.append((name, s))
            except ValueError:
                print(f"Warning: Unknown strategy '{name}' in config")

        if not active_strategies:
            # Fallback
            from app.optimizer.strategies import RefinementStrategy

            active_strategies = [("fallback", RefinementStrategy())]

        target_count = self.config.candidates_per_generation

        strategy_cycle = itertools.cycle(active_strategies)

        for _ in range(target_count):
            name, strategy = next(strategy_cycle)
            new_text = strategy.mutate(parent, self.provider, failures)

            c = Candidate(
                generation=parent.generation + 1,
                parent_id=parent.id,
                prompt_text=new_text,
                mutation_type=name,
            )
            candidates.append(c)

        return candidates
