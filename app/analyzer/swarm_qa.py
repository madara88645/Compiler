from typing import List, Dict
import uuid

from app.llm_engine.schemas import (
    Improvement,
    AgentAnalysis,
    SwarmAnalysisReport,
    QualityReport
)
from app.llm_engine.client import WorkerClient
from app.analyzer.test_scenarios import TestScenariosGenerator

class SwarmAnalyzer:
    """Meta-agent system to analyze, test, and improve Agent Swarm outputs."""

    def __init__(self, client: WorkerClient = None):
        self.client = client or WorkerClient()
        self.test_generator = TestScenariosGenerator(self.client)

    def analyze_swarm(
        self, agents: List[Dict], original_description: str, run_tests: bool = True
    ) -> SwarmAnalysisReport:
        """
        Analyze a generated agent swarm for quality, coherence, and completeness.
        Combines heuristics and LLM-based quality evaluation.
        """
        issues = []
        improvements = []
        per_agent_reports = []

        if not agents:
            return SwarmAnalysisReport(
                issues=["No agents provided for analysis."],
                improvements=[],
                per_agent_reports=[]
            )

        # 1. Heuristic Checks: Role Clarity and Coverage
        roles = [a.get("role", "Unknown").lower() for a in agents]

        # Heuristic 1: Overlapping roles
        role_clarity_score = 100.0
        seen_roles = set()
        for role in roles:
            # Simple keyword overlap check
            base_role = role.split()[-1] # e.g. "Senior Python Developer" -> "developer"
            if base_role in seen_roles and base_role not in ["agent", "assistant"]:
                role_clarity_score -= 15.0
                issues.append(f"Potential role overlap detected: Multiple agents ending with '{base_role}'.")
                improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title="Merge overlapping roles",
                        description=f"Consider merging the agents sharing the '{base_role}' suffix to reduce redundancy.",
                        severity="medium",
                        category="roles",
                        suggested_changes={"merge_targets": [r for r in roles if base_role in r]}
                    )
                )
            seen_roles.add(base_role)
            seen_roles.add(role)

        role_clarity_score = max(0.0, role_clarity_score)

        # Heuristic 2: Coverage (Missing standard roles for a swarm)
        coverage_score = 100.0
        has_planner = any(r for r in roles if "planner" in r or "coordinator" in r or "manager" in r or "router" in r)

        has_reviewer = any(r for r in roles if "reviewer" in r or "validator" in r or "qa" in r or "critic" in r)

        if len(agents) >= 3:
            if not has_planner:
                coverage_score -= 20.0
                issues.append("Missing a coordinating/planning role for a swarm of 3+ agents.")
                improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title="Add Coordinator Agent",
                        description="For swarms with 3 or more agents, a coordinator or planner role is recommended to manage task delegation.",
                        severity="medium",
                        category="coverage"
                    )
                )
            if not has_reviewer:
                coverage_score -= 15.0
                issues.append("Missing a review or validation role to ensure quality output.")
                improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title="Add Reviewer Agent",
                        description="Add a dedicated agent for QA, review, or validation to catch errors before final output.",
                        severity="medium",
                        category="coverage"
                    )
                )

        coverage_score = max(0.0, coverage_score)

        # Heuristic 3: Efficiency
        efficiency_score = 100.0
        if len(agents) > 5:
            efficiency_score -= 30.0
            issues.append(f"High coordination overhead expected with {len(agents)} agents.")
            improvements.append(
                Improvement(
                    id=str(uuid.uuid4()),
                    title="Consolidate Agents",
                    description="Having more than 5 specialized agents increases message passing and context loss. Consolidate related roles.",
                    severity="high",
                    category="communication"
                )
            )

        efficiency_score = max(0.0, efficiency_score)

        # 2. LLM Checks: Prompt Quality per Agent
        prompt_quality_scores = []
        for agent in agents:
            role = agent.get("role", "Unknown Role")
            prompt = agent.get("prompt", "")

            # Use WorkerClient.analyze_prompt which returns a QualityReport
            # Fallback if analyze_prompt fails
            try:
                quality_report = self.client.analyze_prompt(prompt)
                prompt_quality_scores.append(quality_report.score)
            except Exception as e:
                print(f"Failed to analyze prompt for {role}: {e}")
                quality_report = QualityReport(
                    score=50,
                    summary=f"Failed to analyze prompt: {e}",
                    category_scores={"clarity": 50, "specificity": 50, "completeness": 50, "consistency": 50}
                )
                prompt_quality_scores.append(50)

            # Generate agent-specific improvements
            agent_improvements = []
            for weak in quality_report.weaknesses:
                agent_improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title=f"Address weakness in {role} prompt",
                        description=weak,
                        severity="medium",
                        category="prompt_quality"
                    )
                )

            for sugg in quality_report.suggestions:
                agent_improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title=f"Improve {role} prompt",
                        description=sugg,
                        severity="low",
                        category="prompt_quality"
                    )
                )

            per_agent_reports.append(
                AgentAnalysis(
                    agent_name=role,
                    role=role,
                    system_prompt=prompt,
                    quality_report=quality_report,
                    issues=quality_report.weaknesses,
                    suggested_improvements=agent_improvements
                )
            )

        avg_prompt_quality = sum(prompt_quality_scores) / len(prompt_quality_scores) if prompt_quality_scores else 0.0

        # 3. Simulate Tests
        test_results = None
        if run_tests:
            test_results = self.test_generator.test_swarm(agents, original_description)

            # Incorporate test results into scores and issues
            if test_results.success_rate < 50.0:
                efficiency_score -= 10.0
                issues.extend(test_results.failure_modes)
                improvements.append(
                    Improvement(
                        id=str(uuid.uuid4()),
                        title="Address Test Failures",
                        description="Synthetic tests indicated a low success rate. Review failure modes.",
                        severity="high",
                        category="other"
                    )
                )

            if test_results.coordination_overhead == "high":
                efficiency_score -= 15.0

        # 4. Overall Quality Score
        quality_score = (role_clarity_score + coverage_score + efficiency_score + avg_prompt_quality) / 4.0

        return SwarmAnalysisReport(
            quality_score=round(quality_score, 1),
            role_clarity_score=round(role_clarity_score, 1),
            coverage_score=round(coverage_score, 1),
            efficiency_score=round(efficiency_score, 1),
            prompt_quality_score=round(avg_prompt_quality, 1),
            issues=list(set(issues)),  # Deduplicate issues
            improvements=improvements,
            test_results=test_results,
            per_agent_reports=per_agent_reports
        )
