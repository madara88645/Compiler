from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from app.models_v2 import IRv2, DiagnosticItem


class WorkerResponse(BaseModel):
    """
    Full response from Worker LLM.
    Includes IR structure AND direct prompt outputs.
    """

    ir: IRv2 = Field(..., description="Structured IR of the prompt")
    diagnostics: List[DiagnosticItem] = Field(default_factory=list)
    thought_process: str = Field(default="", description="Chain-of-thought reasoning")
    optimized_content: str = Field(
        default="", description="Expanded prompt (legacy or auto-generated)"
    )

    # NEW: Direct prompt outputs (LLM generates these)
    system_prompt: str = Field(default="", description="Ready-to-use system prompt")
    user_prompt: str = Field(default="", description="Ready-to-use user message")
    plan: str = Field(default="", description="Step-by-step plan/approach")

    model_config = ConfigDict(extra="ignore")


class QualityReport(BaseModel):
    """Quality Coach analysis result from Worker LLM."""

    score: int = Field(default=50, ge=0, le=100, description="Overall quality score 0-100")
    category_scores: dict = Field(
        default_factory=lambda: {
            "clarity": 0,
            "specificity": 0,
            "completeness": 0,
            "consistency": 0,
        },
        description="Score breakdown by category",
    )
    strengths: List[str] = Field(default_factory=list, description="What's good about the prompt")
    weaknesses: List[str] = Field(default_factory=list, description="What needs improvement")
    suggestions: List[str] = Field(default_factory=list, description="Actionable improvements")
    summary: str = Field(default="", description="Brief overall assessment")

    model_config = ConfigDict(extra="ignore")


class LLMFixResponse(BaseModel):
    """Auto-fix result from DeepSeek Editor."""

    fixed_text: str = Field(..., description="The improved prompt text")
    explanation: str = Field(default="", description="What changed and why")
    changes: List[str] = Field(default_factory=list, description="List of specific changes applied")

    model_config = ConfigDict(extra="ignore")


# ============================================================================
# Swarm Analyzer Schemas
# ============================================================================


class Improvement(BaseModel):
    id: str = Field(
        ...,
        description="Ephemeral identifier for this improvement (unique within a single analysis run, not stable across runs)",
    )
    title: str = Field(..., description="Short label for the improvement")
    description: str = Field(..., description="Detailed description of what to change and why")
    severity: Literal["low", "medium", "high"] = Field(..., description="Severity of the issue")
    category: Literal["roles", "communication", "coverage", "prompt_quality", "other"] = Field(
        ..., description="Category of the improvement"
    )
    suggested_changes: Optional[Dict] = Field(
        default=None, description="Structured suggestion data (e.g., which agents/fields to edit)"
    )


class AgentAnalysis(BaseModel):
    agent_name: str = Field(..., description="Name of the agent")
    role: str = Field(..., description="Role of the agent")
    system_prompt: str = Field(..., description="System prompt of the agent")
    quality_report: QualityReport = Field(..., description="Quality report for this specific agent")
    issues: List[str] = Field(default_factory=list, description="List of issues for this agent")
    suggested_improvements: List[Improvement] = Field(
        default_factory=list, description="List of improvements scoped to this agent"
    )


class EvaluationResults(BaseModel):
    __test__ = False
    scenarios_run: int = Field(default=0, description="Number of scenarios executed")
    success_rate: float = Field(default=0.0, description="Percentage of scenarios passed")
    failure_modes: List[str] = Field(
        default_factory=list, description="List of failure modes identified"
    )
    coordination_overhead: str = Field(
        default="", description="Assessment of coordination overhead"
    )
    coverage_metrics: Dict[str, float] = Field(
        default_factory=dict, description="Coverage metrics across different task aspects"
    )


class SwarmAnalysisReport(BaseModel):
    quality_score: float = Field(default=0.0, description="Overall quality score (0-100)")
    role_clarity_score: float = Field(default=0.0, description="Role clarity score (0-100)")
    coverage_score: float = Field(default=0.0, description="Coverage score (0-100)")
    efficiency_score: float = Field(default=0.0, description="Efficiency score (0-100)")
    prompt_quality_score: float = Field(default=0.0, description="Prompt quality score (0-100)")

    issues: List[str] = Field(default_factory=list, description="High-level swarm issues")
    improvements: List[Improvement] = Field(
        default_factory=list, description="Actionable recommendations for the swarm"
    )
    test_results: Optional[EvaluationResults] = Field(
        default=None, description="Performance metrics from synthetic tests"
    )
    per_agent_reports: List[AgentAnalysis] = Field(
        default_factory=list, description="Analysis reports for each individual agent"
    )

    model_config = ConfigDict(extra="ignore")


class AgentDefinition(BaseModel):
    """Schema for an individual agent in a swarm definition."""

    role: str = Field(
        ..., max_length=200, description="The role of the agent (e.g., 'planner', 'executor')"
    )
    prompt: str = Field(..., max_length=30000, description="The system prompt for the agent")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional additional metadata for the agent"
    )

    model_config = ConfigDict(extra="ignore")


class SwarmAnalysisRequest(BaseModel):
    agents: List[AgentDefinition] = Field(..., description="List of generated agent definitions")
    original_description: str = Field(
        ..., max_length=8000, description="User's original task request"
    )
    run_tests: bool = Field(default=True, description="Whether to run synthetic test scenarios")
