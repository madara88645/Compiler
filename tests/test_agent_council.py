import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.context_strategist import ContextStrategist  # noqa: E402
from app.optimizer.critic import CriticAgent  # noqa: E402


class TestAgentCouncil(unittest.TestCase):
    def setUp(self):
        # Mock WorkerClient to avoid real API calls during test
        self.mock_client = MagicMock()
        self.mock_client._call_api.return_value = '["mock query 1", "mock query 2"]'

    def test_agent6_context_strategist(self):
        print("\n--- Testing Agent 6: The Context Strategist ---")

        # Initialize
        strategist = ContextStrategist(client=self.mock_client)

        # Test Query Expansion
        base_prompt = "fix auth login bug"
        print(f"Input Prompt: '{base_prompt}'")

        # Mock search_hybrid to return fake results
        with patch("app.agents.context_strategist.search_hybrid") as mock_search:

            def side_effect(q, k):
                if "auth" in q:
                    return [{"path": "auth.py", "content": "def login(): pass", "score": 0.9}]
                return [{"path": "user.py", "content": "class User: pass", "score": 0.5}]

            mock_search.side_effect = side_effect

            results = strategist.retrieve(base_prompt)

            # Verify Query Expansion happened
            self.mock_client._call_api.assert_called_once()
            print("Query Expansion: ✅ (Called LLM)")

            # Verify Retrieval
            print(f"Retrieved {len(results)} snippets.")
            for r in results:
                print(f" - Found: {r['path']} (Score: {r.get('score',0):.2f})")

            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0]["path"], "auth.py")

    def test_agent7_the_critic(self):
        print("\n--- Testing Agent 7: The Critic ---")

        # Setup Mock LLM response for Critic
        critic_response = {
            "verdict": "REJECT",
            "score": 45,
            "issues": [
                {
                    "type": "Hallucination",
                    "description": "Function 'magic_login' does not exist in auth.py",
                    "severity": "Critical",
                }
            ],
            "feedback": "Use 'login_user' instead of 'magic_login'.",
        }
        # USE JSON.DUMPS FOR VALID JSON
        import json

        self.mock_client._call_api.return_value = json.dumps(critic_response)

        critic = CriticAgent(client=self.mock_client)

        # Test Critique
        user_req = "Make a secure login"
        sys_prompt = "You are a coding assistant. Use auth.magic_login()."
        context = "def login_user(): pass"

        print("Critiquing System Prompt against Context...")
        verdict = critic.critique(user_req, sys_prompt, context=context)

        print(f"Verdict: {verdict.verdict}")
        print(f"Score: {verdict.score}/100")
        print(f"Issues Found: {len(verdict.issues)}")
        for issue in verdict.issues:
            print(f" - [{issue.type}] {issue.description}")

        self.assertEqual(verdict.verdict, "REJECT")
        self.assertEqual(verdict.issues[0].type, "Hallucination")


if __name__ == "__main__":
    unittest.main()
