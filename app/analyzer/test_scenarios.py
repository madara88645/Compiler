from typing import List, Dict
import json
from app.llm_engine.schemas import EvaluationResults
from app.llm_engine.client import WorkerClient


class ScenariosGenerator:
    __test__ = False
    """Generates synthetic test scenarios to evaluate a multi-agent swarm."""

    def __init__(self, client: WorkerClient = None):
        self.client = client or WorkerClient()

    def generate_scenarios(self, task_description: str) -> List[str]:
        """
        Use lightweight LLM call to generate 3 specific edge cases or
        complex scenarios for the given task description.
        """
        prompt = (
            f"Given the following task that an AI agent swarm is built to solve:\n"
            f"'{task_description}'\n\n"
            "Generate 3 distinct edge cases or complex synthetic scenarios that test "
            "edge case handling, agent handoffs, conflict resolution, or error recovery. "
            "Return ONLY a JSON array of strings, where each string is a scenario description."
        )

        messages = [
            {"role": "system", "content": "You are a QA automation expert."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.client._call_api(messages, max_tokens=800, json_mode=True)
            scenarios = json.loads(response)
            if isinstance(scenarios, list) and all(isinstance(i, str) for i in scenarios):
                return scenarios
            elif isinstance(scenarios, dict) and "scenarios" in scenarios:
                return scenarios["scenarios"]
        except Exception as e:
            print(f"Error generating test scenarios: {e}")

        # Fallback heuristic scenarios if LLM call fails
        return [
            "A critical input parameter is missing or malformed.",
            "The first agent completes its task but the intermediate output format is misunderstood by the second agent.",
            "An edge case occurs requiring the system to gracefully degrade or report an error back to the user.",
        ]

    def test_swarm(self, agents: List[Dict], original_description: str) -> EvaluationResults:
        """
        Simulate swarm execution using heuristics and a lightweight LLM call.
        """
        scenarios = self.generate_scenarios(original_description)
        failure_modes = []
        successes = 0

        roles = [agent.get("role", "Unknown Role").lower() for agent in agents]

        # Heuristic test: Handoff check
        if (
            not any("coordinator" in r or "router" in r or "planner" in r for r in roles)
            and len(roles) > 2
        ):
            failure_modes.append(
                "Potential handoff failure: Missing central coordinator or planner for a large swarm."
            )

        # Heuristic test: Conflict resolution
        if not any("validator" in r or "reviewer" in r or "critic" in r for r in roles):
            failure_modes.append(
                "Missing conflict resolution: No validator role identified to catch errors."
            )

        # Simulate execution for one complex scenario to see if the LLM thinks they can handle it
        scenario_to_test = scenarios[0] if scenarios else "General task execution"

        agent_descriptions = "\n".join(
            [
                f"- Role: {a.get('role')} | Prompt summary: {a.get('prompt', '')[:100]}..."
                for a in agents
            ]
        )

        eval_prompt = (
            f"You are evaluating a multi-agent swarm designed to handle: '{original_description}'.\n"
            f"The swarm has the following agents:\n{agent_descriptions}\n\n"
            f"Evaluate how this swarm handles the following scenario: '{scenario_to_test}'.\n"
            "Assess if the handoffs are clear, if responsibilities cover the scenario, and if there is coordination overhead. "
            "Return ONLY a JSON object with the following keys:\n"
            "- success: boolean\n"
            "- failure_mode: string (optional, what went wrong if success is false)\n"
            "- coordination_overhead: string (low/medium/high overhead)\n"
            "- coverage_score: float (0.0 to 100.0, how well the scenario is covered)\n"
        )

        messages = [
            {"role": "system", "content": "You are a test orchestrator for multi-agent systems."},
            {"role": "user", "content": eval_prompt},
        ]

        coordination_overhead = "medium"
        coverage_metrics = {"scenario_1": 50.0}

        try:
            response = self.client._call_api(messages, max_tokens=500, json_mode=True)
            eval_result = json.loads(response)

            if eval_result.get("success"):
                successes += 1
            elif eval_result.get("failure_mode"):
                failure_modes.append(eval_result["failure_mode"])

            coordination_overhead = eval_result.get("coordination_overhead", "medium")
            coverage_metrics["scenario_1"] = float(eval_result.get("coverage_score", 50.0))

        except Exception as e:
            print(f"Error evaluating scenario: {e}")
            failure_modes.append("LLM Evaluation failed to determine success.")

        # Calculate metrics
        success_rate = (successes / 1) * 100.0 if scenarios else 0.0  # Only testing 1 for speed

        return EvaluationResults(
            scenarios_run=1,
            success_rate=success_rate,
            failure_modes=failure_modes,
            coordination_overhead=coordination_overhead,
            coverage_metrics=coverage_metrics,
        )
