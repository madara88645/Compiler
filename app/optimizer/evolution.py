from __future__ import annotations
from pathlib import Path

from typing import Optional, List
from app.testing.models import TestSuite
from .models import Candidate, OptimizationConfig, OptimizationRun
from .mutator import MutatorAgent
from .judge import JudgeAgent
from app.testing.adversarial import AdversarialGenerator
from .callbacks import EvolutionCallback
from .costs import CostTracker, TokenCounter
from .validator import CrossModelValidator
from app.llm.factory import get_provider
from app.llm.base import ProviderConfig


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
        self.history_manager = HistoryManager()
        self.cost_tracker = CostTracker()

        # Initialize Cross-Model Validator
        self.validator = None
        if config.validation_models:
            print(f"Initializing Cross-Model Validator with: {config.validation_models}")
            val_providers = {}
            for model_spec in config.validation_models:
                # Simple heuristic to determine provider
                # Format could be "provider:model" or just "model"
                if ":" in model_spec:
                    provider_name, model_name = model_spec.split(":", 1)
                else:
                    # Guess provider
                    model_lower = model_spec.lower()
                    if "gpt" in model_lower or "o1" in model_lower:
                        provider_name = "openai"
                    elif "claude" in model_lower:
                        provider_name = "anthropic"  # Not in factory yet, fallback or error?
                        # Using openai for compatible endpoints or error if not valid
                        # Assuming factory handles unknown names gracefully or we catch it
                        # For this impl, map commonly known ones, else default to ollama
                        pass
                    else:
                        provider_name = "ollama"
                    model_name = model_spec

                try:
                    # Create separate config for validation model
                    # For simplicty, reuse env vars for API keys but change model
                    p_config = ProviderConfig(model=model_name)
                    provider = get_provider(provider_name, config=p_config)
                    val_providers[model_spec] = provider
                except Exception as e:
                    print(f"Warning: Failed to load validation model {model_spec}: {e}")

            if val_providers:
                self.validator = CrossModelValidator(val_providers)

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

        best = baseline
        if callback:
            callback.on_new_best(best, best.score)

        # Initialize cost tracking
        self.run_history.total_cost = 0.0

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

        # Restore Cost State
        self.cost_tracker.total_cost = run.total_cost
        print(f"Resuming with accumulated cost: ${run.total_cost:.4f}")

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
    ) -> List[Candidate]:
        """
        Hook for human-in-the-loop intervention.
        Handles both direct edits and high-level feedback ("Director Mode").
        """
        if not callback or not hasattr(callback, "on_human_intervention_needed"):
            return []

        # Request user input
        # Note: Callback might return a str (edit) or a dict (structured command)
        response = callback.on_human_intervention_needed(current_best, generation)

        if not response:
            return []

        new_candidates = []

        # Case A: Structured Response (Dict)
        if isinstance(response, dict):
            resp_type = response.get("type")
            content = response.get("content")

            if resp_type == "feedback" and content:
                print(f"🎬 Director Mode: Applying feedback '{content[:50]}...'")
                # Use Mutator to generate variations based on feedback
                generated = self.mutator.apply_director_feedback(current_best, content)
                new_candidates.extend(generated)

            elif resp_type == "edit" and content:
                print("Manual edit received.")
                # Create candidate directly
                new_candidates.append(
                    Candidate(
                        generation=generation,
                        parent_id=current_best.id,
                        prompt_text=content.strip(),
                        mutation_type="human_edit",
                    )
                )

        # Case B: Legacy String Response (Direct Edit)
        elif isinstance(response, str) and response.strip():
            print("Manual edit received.")
            new_candidates.append(
                Candidate(
                    generation=generation,
                    parent_id=current_best.id,
                    prompt_text=response.strip(),
                    mutation_type="human_edit",
                )
            )

        # Evaluate all new candidates
        for cand in new_candidates:
            self._evaluate_candidate(cand, suite, base_dir)
            if callback:
                callback.on_candidate_evaluated(cand, cand.result)
            print(f"Human intervention candidate evaluated: score={cand.score:.2f}")

        return new_candidates

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

            # Budget Check
            current_cost = self.cost_tracker.estimated_cost()
            if self.config.budget_limit and current_cost >= self.config.budget_limit:
                print(f"🛑 Budget Limit of ${self.config.budget_limit} reached! Stopping.")
                break

            print(
                f"gen {gen}: Evolving from best candidate (score={best.score:.2f})... [Cost so far: ${current_cost:.4f}]"
            )

            # Selection: Pick top K candidates to mutate (Steepest Ascent for now, just top 1)
            parent = best

            # Mutation
            failures = parent.result.failures if parent.result else []
            new_candidates = self.mutator.generate_variations(parent, failures)

            # Track Cost
            # Estimate: Input = Parent + System Prompt(~500), Output = New Candidates
            in_tokens = TokenCounter.count(parent.prompt_text, self.config.model) + 500
            out_tokens = sum(
                TokenCounter.count(c.prompt_text, self.config.model) for c in new_candidates
            )
            self.cost_tracker.add_usage(in_tokens, out_tokens, self.config.model)

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
                    best = cand
                    if callback:
                        callback.on_new_best(best, best.score)

                    # Trigger Cross-Model Validation for new best
                    self._run_cross_validation(best, suite)

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
                human_candidates = self._request_human_intervention(
                    current_best=best,
                    generation=gen,
                    suite=suite,
                    base_dir=base_dir,
                    callback=callback,
                )

                if human_candidates:
                    # Inject into pool
                    current_pool.extend(human_candidates)

                    # Update best if any new candidate is better
                    for hc in human_candidates:
                        if hc.score > best.score:
                            best = hc
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
        self.run_history.total_cost = self.cost_tracker.total_cost

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

    def _run_cross_validation(self, candidate: Candidate, suite: TestSuite):
        """Run cross-model validation on the candidate."""
        if not self.validator:
            return

        print(f"⚡ Running Cross-Model Validation on candidate {candidate.id}...")
        try:
            results = self.validator.validate(candidate.prompt_text, suite.test_cases)
            candidate.metadata["validation_scores"] = results.scores
            print(f"   Validation Scores: {results.scores}")
        except Exception as e:
            print(f"   ❌ Validation failed: {e}")
