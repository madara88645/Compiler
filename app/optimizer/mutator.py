from __future__ import annotations
import json
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

    def apply_director_feedback(self, parent: Candidate, feedback: str) -> List[Candidate]:
        """
        Apply specific human feedback ("Director Mode") to generate variations.
        """
        if not self.provider:
            # Fallback for mock/test
            return [
                Candidate(
                    generation=parent.generation + 1,
                    parent_id=parent.id,
                    prompt_text=f"{parent.prompt_text}\n\n[Applied Feedback: {feedback}]",
                    mutation_type="director_feedback",
                )
            ]

        # Director System Prompt
        system_prompt = """You are an Intelligent Prompt Engineer working in 'Director Mode'.
Your Goal: Implement the Director's specific feedback to improve the prompt.

Input:
1. "Current Prompt": The prompt to modify.
2. "Director's Feedback": Specific instructions on what to change (e.g., "Make it more professional", "Fix the JSON format").

Your Task:
Generate 2 variations that implement this feedback in slightly different ways.
- Variation 1 (literal): Follow the feedback exactly.
- Variation 2 (creative): Follow the feedback but also optimize for flow/clarity.

Output Format:
Return ONLY a valid JSON object:
{
  "variations": [
    { "type": "director_literal", "prompt": "..." },
    { "type": "director_creative", "prompt": "..." }
  ]
}"""

        user_prompt = f"""Current Prompt:
{parent.prompt_text}

Director's Feedback:
{feedback}"""

        try:
            response = self.provider.generate(user_prompt, system_prompt=system_prompt)
            data = json.loads(response.content)
            variations = data.get("variations", [])

            candidates = []
            for var in variations:
                c = Candidate(
                    generation=parent.generation + 1,
                    parent_id=parent.id,
                    prompt_text=var.get("prompt", parent.prompt_text),
                    mutation_type=var.get("type", "director_feedback"),
                )
                candidates.append(c)

            return candidates

        except Exception as e:
            print(f"[MutatorAgent] Director feedback failed: {e}")
            return [
                Candidate(
                    generation=parent.generation + 1,
                    parent_id=parent.id,
                    prompt_text=f"{parent.prompt_text}\n\n[Applied Feedback: {feedback}]",
                    mutation_type="director_feedback_fallback",
                )
            ]
