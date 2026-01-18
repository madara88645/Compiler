from __future__ import annotations
from pathlib import Path

from app.testing.models import TestSuite
from .models import Candidate, OptimizationConfig, OptimizationRun
from .mutator import MutatorAgent
from .judge import JudgeAgent


class EvolutionEngine:
    """
    Agent 1: The Orchestrator (Evolution Engine).
    Manages the optimization loop.
    """

    def __init__(self, config: OptimizationConfig, judge: JudgeAgent, mutator: MutatorAgent):
        self.config = config
        self.judge = judge
        self.mutator = mutator
        self.run_history = OptimizationRun(config=config)

    def run(self, initial_prompt: str, suite: TestSuite, base_dir: Path) -> Candidate:
        """
        Execute the evolutionary optimization loop.
        """

        # Generation 0: The Baseline
        baseline = Candidate(generation=0, prompt_text=initial_prompt, mutation_type="baseline")

        # Evaluate Baseline
        self._evaluate_candidate(baseline, suite, base_dir)

        current_pool = [baseline]
        self.run_history.generations.append(current_pool)

        best = baseline

        print(
            f"gen 0: Baseline Score = {baseline.score:.2f} ({baseline.result.passed_count}/{len(suite.test_cases)})"
        )

        # Evolution Loop
        for gen in range(1, self.config.max_generations + 1):
            if best.score >= self.config.target_score:
                print("Target score reached!")
                break

            print(f"gen {gen}: Evolving from best candidate (score={best.score:.2f})...")

            # Selection: Pick top K candidates to mutate (Steepest Ascent for now, just top 1)
            # Future: Deterministic crowd selection
            parent = best

            # Mutation (Agent 3)
            # Use failures from the parent's evaluation to guide mutation
            failures = parent.result.failures if parent.result else []
            new_candidates = self.mutator.generate_variations(parent, failures)

            # Evaluation (Agent 2)
            evaluated_candidates = []
            for cand in new_candidates:
                self._evaluate_candidate(cand, suite, base_dir)
                evaluated_candidates.append(cand)

                if cand.score > best.score:
                    best = cand

            current_pool = evaluated_candidates
            self.run_history.generations.append(current_pool)

            # Reporting
            top_gen_score = max(c.score for c in evaluated_candidates)
            print(f"gen {gen}: Top Score in Generation = {top_gen_score:.2f}")

        self.run_history.best_candidate = best
        return best

    def _evaluate_candidate(self, candidate: Candidate, suite: TestSuite, base_dir: Path):
        """Helper to run the judge and attach result to candidate."""
        result = self.judge.evaluate(candidate, suite, base_dir)
        candidate.result = result
