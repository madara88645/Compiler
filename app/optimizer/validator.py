"""
Cross-Model Validation Service.
Evaluates prompts against multiple LLM models to ensure robustness.
"""

from __future__ import annotations
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field

from app.llm.base import LLMProvider
from app.testing.models import TestSuite, TestCase
from app.optimizer.judge import JudgeAgent, EvaluationResult
from app.optimizer.models import Candidate


class ModelScore(BaseModel):
    """Score from a specific validation model."""

    model_name: str
    score: float
    passed: bool
    details: Optional[EvaluationResult] = None
    error: Optional[str] = None


class ValidationResult(BaseModel):
    """Aggregated result from cross-model validation."""

    scores: Dict[str, float] = Field(default_factory=dict)
    detailed_results: List[ModelScore] = Field(default_factory=list)

    @property
    def average_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


class CrossModelValidator:
    """
    Validates prompts using multiple models in parallel.
    """

    def __init__(self, validation_models: Dict[str, LLMProvider]):
        """
        Args:
            validation_models: Dict mapping model friendly name (e.g., 'claude') to Provider instance.
        """
        self.validation_models = validation_models

    def validate(self, prompt_text: str, test_cases: List[TestCase]) -> ValidationResult:
        """
        Run the prompt against all configured validation models.
        """
        # Create a temporary suite for evaluation
        # We reuse the logic in JudgeAgent, which requires a TestSuite object.
        suite = TestSuite(
            name="ValidationSuite",
            prompt_file="memory",  # Not used directly by judge when candidate text provided
            test_cases=test_cases,
        )

        candidate = Candidate(generation=0, prompt_text=prompt_text, mutation_type="validation")

        results = []

        # We use a ThreadPoolExecutor to run validations in parallel.
        # Although the JudgeAgent is synchronous, the underlying LLM calls are I/O bound.
        with ThreadPoolExecutor(max_workers=len(self.validation_models)) as executor:
            future_to_model = {
                executor.submit(self._evaluate_single_model, name, provider, candidate, suite): name
                for name, provider in self.validation_models.items()
            }

            for future in as_completed(future_to_model):
                model_name = future_to_model[future]
                try:
                    score_result = future.result()
                    results.append(score_result)
                except Exception as e:
                    print(f"[CrossModelValidator] Error with model {model_name}: {e}")
                    results.append(
                        ModelScore(model_name=model_name, score=0.0, passed=False, error=str(e))
                    )

        # Aggregate results
        final_scores = {}
        for res in results:
            if not res.error:
                final_scores[res.model_name] = res.score

        return ValidationResult(scores=final_scores, detailed_results=results)

    def _evaluate_single_model(
        self, name: str, provider: LLMProvider, candidate: Candidate, suite: TestSuite
    ) -> ModelScore:
        """
        Helper to run evaluation for a single model.
        """
        try:
            # Instantiate a Judge specifically for this provider
            # This sets up a TestRunner linked to this provider
            judge = JudgeAgent(provider=provider)

            # Use base_dir as current dir (.), logic doesn't heavily depend on it if file reading is skipped
            # JudgeAgent.evaluate iterates cases manually using candidate text.
            from pathlib import Path

            result = judge.evaluate(candidate, suite, Path("."))

            error_msg = None
            if result.error_count > 0:
                # Extract first error message from failures
                # Failure format in JudgeAgent: "[{case.id}] Error: {result.error}"
                for f in result.failures:
                    if "Error: " in f:
                        parts = f.split("Error: ", 1)
                        if len(parts) > 1:
                            error_msg = parts[1]
                            break
                if not error_msg:
                    error_msg = "Unknown execution error"

            return ModelScore(
                model_name=name,
                score=result.score,
                passed=result.score >= 1.0,  # Strict validation? Or threshold?
                details=result,
                error=error_msg,
            )
        except Exception as e:
            return ModelScore(model_name=name, score=0.0, passed=False, error=str(e))
