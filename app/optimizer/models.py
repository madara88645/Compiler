from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class OptimizationConfig(BaseModel):
    """Configuration for the optimization process."""

    max_generations: int = 3
    candidates_per_generation: int = 3
    target_score: float = 1.0  # Stop if this score is reached
    model: str = "gpt-4o"  # Model used for the Mutation Agent
    custom_system_prompt: Optional[str] = None


class EvaluationResult(BaseModel):
    """The result of a candidate's evaluation by the Judge."""

    score: float  # 0.0 to 1.0
    passed_count: int
    failed_count: int
    error_count: int
    avg_latency_ms: float
    failures: List[str] = Field(default_factory=list)  # Summaries of failures


class Candidate(BaseModel):
    """A single prompt candidate in the evolutionary pool."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    generation: int
    parent_id: Optional[str] = None
    prompt_text: str
    mutation_type: str = "initial"  # e.g., "refinement", "creative"

    # Evaluation state
    result: Optional[EvaluationResult] = None

    @property
    def score(self) -> float:
        return self.result.score if self.result else 0.0


class OptimizationRun(BaseModel):
    """Record of a full optimization session."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    config: OptimizationConfig
    generations: List[List[Candidate]] = Field(default_factory=list)
    best_candidate: Optional[Candidate] = None
