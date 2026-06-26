# ruff: noqa: E402
from app.analyzer.swarm_qa import SwarmAnalyzer


def test_swarm_analyzer_basic():
    """Basic integration test for SwarmAnalyzer logic."""
    # Simple check for report generation structure
    analyzer = SwarmAnalyzer()
    assert analyzer is not None
    assert hasattr(analyzer, "analyze_swarm")


def test_swarm_analyzer_report_structure_placeholder():
    """Synchronous placeholder for structure tests."""
    pass


from unittest.mock import MagicMock
import json
from app.analyzer.test_scenarios import ScenariosGenerator
from app.llm_engine.schemas import QualityReport


def test_scenarios_generator_success():
    client = MagicMock()
    # Mock successful JSON array response for scenario generation
    client._call_api.return_value = json.dumps(["scenario 1", "scenario 2", "scenario 3"])

    generator = ScenariosGenerator(client)
    scenarios = generator.generate_scenarios("A task description")
    assert scenarios == ["scenario 1", "scenario 2", "scenario 3"]
    client._call_api.assert_called_once()


def test_scenarios_generator_fallback():
    client = MagicMock()
    # Simulate API exception
    client._call_api.side_effect = Exception("API error")

    generator = ScenariosGenerator(client)
    scenarios = generator.generate_scenarios("A task description")
    # Verify fallback scenarios are returned
    assert len(scenarios) == 3
    assert "A critical input parameter is missing or malformed." in scenarios


def test_scenarios_generator_test_swarm_success():
    client = MagicMock()
    # Mock calls for generate_scenarios and test_swarm evaluation
    client._call_api.side_effect = [
        json.dumps(["scenario 1", "scenario 2", "scenario 3"]),
        json.dumps({"success": True, "coverage_score": 85.0, "coordination_overhead": "low"}),
    ]

    generator = ScenariosGenerator(client)
    agents = [
        {"role": "Coordinator Agent", "prompt": "system prompt 1"},
        {"role": "Writer Agent", "prompt": "system prompt 2"},
    ]

    res = generator.test_swarm(agents, "Original task")
    assert res.scenarios_run == 1
    assert res.success_rate == 100.0
    assert res.coordination_overhead == "low"
    assert res.coverage_metrics["scenario_1"] == 85.0


def test_scenarios_generator_test_swarm_failure():
    client = MagicMock()
    client._call_api.side_effect = [
        json.dumps(["scenario 1"]),
        json.dumps(
            {
                "success": False,
                "failure_mode": "coordination bottleneck",
                "coverage_score": 40.0,
                "coordination_overhead": "high",
            }
        ),
    ]

    generator = ScenariosGenerator(client)
    agents = [
        {"role": "Developer Agent", "prompt": "system prompt 1"},
        {"role": "QA Agent", "prompt": "system prompt 2"},
    ]

    res = generator.test_swarm(agents, "Original task")
    assert res.success_rate == 0.0
    assert "coordination bottleneck" in res.failure_modes
    assert res.coordination_overhead == "high"


def test_swarm_analyzer_empty_agents():
    analyzer = SwarmAnalyzer()
    res = analyzer.analyze_swarm([], "Original task")
    assert "No agents provided for analysis." in res.issues


def test_swarm_analyzer_heuristics_and_llm():
    client = MagicMock()
    # Mock client.analyze_prompt to return a dummy QualityReport
    dummy_report = QualityReport(
        score=75,
        category_scores={"clarity": 75, "specificity": 75, "completeness": 75, "consistency": 75},
        strengths=["clear role"],
        weaknesses=["missing edge cases"],
        suggestions=["add more detail"],
        summary="fair prompt",
    )
    client.analyze_prompt.return_value = dummy_report

    # Mock client._call_api inside test_generator
    client._call_api.side_effect = [
        json.dumps(["scenario 1"]),
        json.dumps({"success": True, "coverage_score": 90.0, "coordination_overhead": "low"}),
    ]

    analyzer = SwarmAnalyzer(client)

    # Test heuristics:
    # 1. Overlapping roles: multiple agents ending with "developer"
    # 2. Missing coordinator/reviewer check: 3+ agents without planner/reviewer
    agents = [
        {"role": "Python Developer", "prompt": "prompt 1"},
        {"role": "Java Developer", "prompt": "prompt 2"},
        {"role": "Tester", "prompt": "prompt 3"},
    ]

    res = analyzer.analyze_swarm(agents, "Task description", run_tests=True)
    assert res.quality_score > 0
    assert any("role overlap" in issue.lower() for issue in res.issues)
    assert any("coordinating/planning role" in issue.lower() for issue in res.issues)
    assert any("validation role" in issue.lower() for issue in res.issues)
    assert len(res.per_agent_reports) == 3


def test_swarm_analyzer_efficiency_check():
    client = MagicMock()
    client.analyze_prompt.return_value = QualityReport(score=80)
    client._call_api.side_effect = [json.dumps(["scenario 1"]), json.dumps({"success": True})]

    analyzer = SwarmAnalyzer(client)

    # Over 5 agents triggers high coordination overhead warning
    agents = [{"role": f"Agent {i}", "prompt": "prompt"} for i in range(6)]

    res = analyzer.analyze_swarm(agents, "Task", run_tests=True)
    assert any("high coordination overhead" in issue.lower() for issue in res.issues)
