from __future__ import annotations
import json
from typing import List, Optional
from .models import Candidate, OptimizationConfig
from app.llm.base import LLMProvider


class MutatorAgent:
    """
    Agent 3: The Mutator.
    Responsible for generating new prompt variations based on feedback.
    """

    SYSTEM_PROMPT = """You are an Expert Prompt Engineer and LLM Optimization Specialist.
Your Goal: Improve a given prompt to maximize its performance on a specific test suite.

Input:
1. "Current Prompt": The prompt text we are optimizing.
2. "Failures": A list of test cases that failed, including the expected output and the actual output.

Your Task:
Generate 3 distinct variations of the "Current Prompt".
- Variation 1 (Refinement): Fix the specific errors found in the Failures.
- Variation 2 (Structural): Change the format (e.g., add Markdown headers, use XML tags).
- Variation 3 (Creative): Try a different persona or framing strategy.

Output Format:
Return ONLY a valid JSON object with the following structure:
{
  "variations": [
    { "type": "refinement", "prompt": "..." },
    { "type": "structural", "prompt": "..." },
    { "type": "creative", "prompt": "..." }
  ]
}
"""

    def __init__(self, config: OptimizationConfig, provider: Optional[LLMProvider] = None):
        self.config = config
        self.provider = provider

    def generate_variations(self, parent: Candidate, failures: List[str]) -> List[Candidate]:
        """
        Calls the LLM to mutate the parent prompt.
        Falls back to mock logic if no provider is configured.
        """
        new_generation = parent.generation + 1

        # Use LLM if provider is available
        if self.provider:
            return self._generate_with_llm(parent, failures, new_generation)

        # Fallback to mock logic
        return self._mock_generate(parent, new_generation)

    def _generate_with_llm(
        self, parent: Candidate, failures: List[str], new_generation: int
    ) -> List[Candidate]:
        """Generate variations using the LLM provider."""
        user_prompt = f"""Current Prompt:
{parent.prompt_text}

Failures:
{chr(10).join(f'- {f}' for f in failures) if failures else 'None'}

Generate 3 variations to improve this prompt."""

        try:
            response = self.provider.generate(user_prompt, system_prompt=self.SYSTEM_PROMPT)
            data = json.loads(response.content)
            variations = data.get("variations", [])

            candidates = []
            for var in variations:
                c = Candidate(
                    generation=new_generation,
                    parent_id=parent.id,
                    prompt_text=var.get("prompt", parent.prompt_text),
                    mutation_type=var.get("type", "unknown"),
                )
                candidates.append(c)

            # Ensure at least one candidate
            if not candidates:
                return self._mock_generate(parent, new_generation)

            return candidates

        except (json.JSONDecodeError, Exception) as e:
            # Log error and fallback to mock
            print(f"[MutatorAgent] LLM generation failed: {e}, using mock fallback")
            return self._mock_generate(parent, new_generation)

    def _mock_generate(self, parent: Candidate, new_generation: int) -> List[Candidate]:
        """Mock mutation for testing without an LLM."""
        candidates = []

        # Variation 1: Refinement (Mock)
        c1 = Candidate(
            generation=new_generation,
            parent_id=parent.id,
            prompt_text=parent.prompt_text + "\n\nIMPORTANT: Ensure you mention memory safety.",
            mutation_type="refinement",
        )
        candidates.append(c1)

        # Variation 2: Structural (Mock)
        c2 = Candidate(
            generation=new_generation,
            parent_id=parent.id,
            prompt_text="### Instructions\n" + parent.prompt_text,
            mutation_type="structural",
        )
        candidates.append(c2)

        # Variation 3: Creative (Mock)
        c3 = Candidate(
            generation=new_generation,
            parent_id=parent.id,
            prompt_text="You are a helpful assistant.\n" + parent.prompt_text,
            mutation_type="creative",
        )
        candidates.append(c3)

        return candidates
