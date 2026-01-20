from __future__ import annotations
from pathlib import Path

from typing import Optional
from app.testing.models import TestSuite
from .models import Candidate, OptimizationConfig, OptimizationRun
from .mutator import MutatorAgent
from .judge import JudgeAgent
from .callbacks import EvolutionCallback


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

        # Initialize HistoryManager
        from .history import HistoryManager

        self.history_manager = HistoryManager()

    def run(
        self,
        initial_prompt: str,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback] = None,
    ) -> Candidate:
        """
        Start a new optimization run.
        """
        if callback:
            callback.on_start(initial_prompt, self.config.target_score)

        # Generation 0: The Baseline
        baseline = Candidate(generation=0, prompt_text=initial_prompt, mutation_type="baseline")

        # Evaluate Baseline
        self._evaluate_candidate(baseline, suite, base_dir)

        if callback:
            callback.on_candidate_evaluated(baseline, baseline.result)

        current_pool = [baseline]
        self.run_history.generations.append(current_pool)

        best = baseline
        if callback:
            callback.on_new_best(best, best.score)

        print(
            f"gen 0: Baseline Score = {baseline.score:.2f} ({baseline.result.passed_count}/{len(suite.test_cases)})"
        )

        return self._run_evolution_loop(
            start_gen=1, best_candidate=best, suite=suite, base_dir=base_dir, callback=callback
        )

    def resume_from(
        self,
        run_id: str,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback] = None,
        extra_generations: int = 0,
    ) -> Candidate:
        """
        Resume an existing optimization run.
        """
        # Load run
        run = self.history_manager.load_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Hydrate state
        self.run_history = run
        self.config = run.config  # Use original config? Or allow update?
        # For now, stick to original config but extend max_generations if requested.

        if extra_generations > 0:
            self.config.max_generations += extra_generations
            print(f"Resuming run {run_id}: Extending to {self.config.max_generations} generations.")
        else:
            print(f"Resuming run {run_id}")

        # Find best candidate so far
        # We could rely on run.best_candidate, but let's re-scan generations to be safe/robust
        best = None
        for gen in run.generations:
            for cand in gen:
                if best is None or cand.score > best.score:
                    best = cand

        if not best:
            raise ValueError("Corrupt run history: No candidates found.")

        if callback:
            callback.on_start(best.prompt_text, self.config.target_score)
            callback.on_new_best(best, best.score)

        start_gen = len(run.generations)
        return self._run_evolution_loop(
            start_gen=start_gen,
            best_candidate=best,
            suite=suite,
            base_dir=base_dir,
            callback=callback,
        )

    def _run_evolution_loop(
        self,
        start_gen: int,
        best_candidate: Candidate,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback],
    ) -> Candidate:
        """
        Shared evolution loop.
        """
        best = best_candidate

        # Evolution Loop
        for gen in range(start_gen, self.config.max_generations + 1):
            if callback:
                callback.on_generation_start(gen)

            if best.score >= self.config.target_score:
                print("Target score reached!")
                break

            print(f"gen {gen}: Evolving from best candidate (score={best.score:.2f})...")

            # Selection: Pick top K candidates to mutate (Steepest Ascent for now, just top 1)
            parent = best

            # Mutation
            failures = parent.result.failures if parent.result else []
            new_candidates = self.mutator.generate_variations(parent, failures)

            # Evaluation
            evaluated_candidates = []
            for cand in new_candidates:
                cand.generation = gen  # Ensure correct generation
                self._evaluate_candidate(cand, suite, base_dir)
                evaluated_candidates.append(cand)

                if callback:
                    callback.on_candidate_evaluated(cand, cand.result)

                if cand.score > best.score:
                    best = cand
                    if callback:
                        callback.on_new_best(best, best.score)

            current_pool = evaluated_candidates
            self.run_history.generations.append(current_pool)

            # Reporting
            if evaluated_candidates:
                top_gen_score = max(c.score for c in evaluated_candidates)
                print(f"gen {gen}: Top Score in Generation = {top_gen_score:.2f}")
            else:
                print(f"gen {gen}: No valid candidates generated.")

        self.run_history.best_candidate = best

        # Save History (Update existing run file)
        try:
            saved_path = self.history_manager.save_run(self.run_history)
            print(f"Optimization run saved to: {saved_path}")
        except Exception as e:
            print(f"Failed to save optimization run: {e}")

        if callback:
            callback.on_complete(best)

        return best

    def _evaluate_candidate(self, candidate: Candidate, suite: TestSuite, base_dir: Path):
        """Helper to run the judge and attach result to candidate."""
        result = self.judge.evaluate(candidate, suite, base_dir)
        candidate.result = result
