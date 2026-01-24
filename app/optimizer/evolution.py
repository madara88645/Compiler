from __future__ import annotations
from pathlib import Path

from typing import Optional
from app.testing.models import TestSuite
from .models import Candidate, OptimizationConfig, OptimizationRun
from .mutator import MutatorAgent
from .judge import JudgeAgent
from app.testing.adversarial import AdversarialGenerator
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

        # Initialize Adversarial Generator (borrowing provider from mutator if possible)
        provider = getattr(mutator, "provider", None)
        self.adversarial = AdversarialGenerator(provider=provider)

        # Initialize HistoryManager
        from .history import HistoryManager

        self.history_manager = HistoryManager()

    def run(
        self,
        initial_prompt: str,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback] = None,
    ) -> OptimizationRun:
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
    ) -> OptimizationRun:
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

    def _request_human_intervention(
        self,
        current_best: Candidate,
        generation: int,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback],
    ) -> Optional[Candidate]:
        """
        Hook for human-in-the-loop intervention.

        Returns a new Candidate if human provided input, None otherwise.
        """
        if not callback:
            return None

        # Check if callback has the method (Protocol compliance)
        if not hasattr(callback, "on_human_intervention_needed"):
            return None

        # Request human input via callback
        new_prompt = callback.on_human_intervention_needed(current_best, generation)

        if new_prompt and new_prompt.strip():
            # Create new candidate from human input
            human_candidate = Candidate(
                generation=generation,
                parent_id=current_best.id,
                prompt_text=new_prompt.strip(),
                mutation_type="human_intervention",
            )

            # Evaluate the human-provided candidate
            self._evaluate_candidate(human_candidate, suite, base_dir)

            print(f"Human candidate evaluated: score={human_candidate.score:.2f}")

            if callback:
                callback.on_candidate_evaluated(human_candidate, human_candidate.result)

            return human_candidate

        return None

    def _run_evolution_loop(
        self,
        start_gen: int,
        best_candidate: Candidate,
        suite: TestSuite,
        base_dir: Path,
        callback: Optional[EvolutionCallback],
    ) -> OptimizationRun:
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

            # Human-in-the-loop check
            if (
                self.config.interactive_every > 0
                and gen > 0
                and gen % self.config.interactive_every == 0
            ):
                human_candidate = self._request_human_intervention(
                    current_best=best,
                    generation=gen,
                    suite=suite,
                    base_dir=base_dir,
                    callback=callback,
                )
                if human_candidate:
                    # Inject into pool and potentially update best
                    current_pool.append(human_candidate)
                    if human_candidate.score > best.score:
                        best = human_candidate
                        if callback:
                            callback.on_new_best(best, best.score)

            # Adversarial Testing Check
            if (
                self.config.adversarial_every > 0
                and gen > 0
                and gen % self.config.adversarial_every == 0
            ):
                print(f"gen {gen}: Generating adversarial test cases...")
                adv_cases = self.adversarial.generate(best.prompt_text)
                if adv_cases:
                    print(f"gen {gen}: Running {len(adv_cases)} adversarial cases.")
                    # Create a temporary suite with these cases
                    # Note: In a real system we might merge them into the main suite or run separately.
                    # Here we just run them against the best candidate to see if it survives.

                    # For metrics, we could track 'adversarial_score'.
                    # For now, let's just log them or potentially penalize?
                    # The prompt implies 'Adversarial Testing workflow' validation.
                    # We will run them and print results.

                    adv_suite = TestSuite(
                        name=f"Adversarial-Gen{gen}",
                        prompt_file=suite.prompt_file,  # Reuse
                        test_cases=adv_cases,
                        defaults=suite.defaults,
                    )

                    # Run evaluation
                    # We create a temporary candidate clone to avoid polluting the main result stats immediately
                    # unless we want to track it.
                    adv_res = self.judge.evaluate(best, adv_suite, base_dir)
                    print(
                        f"Adversarial Score: {adv_res.score:.2f} ({adv_res.passed_count}/{len(adv_cases)})"
                    )

                    # TODO: If score is low, maybe we should mutate specifically to fix these?

        self.run_history.best_candidate = best

        # Save History (Update existing run file)
        try:
            saved_path = self.history_manager.save_run(self.run_history)
            print(f"Optimization run saved to: {saved_path}")
        except Exception as e:
            print(f"Failed to save optimization run: {e}")

        if callback:
            callback.on_complete(best)

        return self.run_history

    def _evaluate_candidate(self, candidate: Candidate, suite: TestSuite, base_dir: Path):
        """Helper to run the judge and attach result to candidate."""
        result = self.judge.evaluate(candidate, suite, base_dir)
        candidate.result = result
