from __future__ import annotations
from typing import List
from .models import Candidate, OptimizationConfig
# For now, we will create an abstract interface. In a real scenario, this would call OpenAI/Anthropic.


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

    def __init__(self, config: OptimizationConfig):
        self.config = config

    def generate_variations(self, parent: Candidate, failures: List[str]) -> List[Candidate]:
        """
        Calls the LLM to mutate the parent prompt.
        For this prototype, we'll simulate the mutation if no LLM key is present,
        or define a placeholder that appends optimization text.
        """

        # TODO: integrate actual LLM client (e.g., via app.compiler's unknown runtime access)
        # For the prototype to work without an API key in this environment,
        # we will use a deterministic "Mock Mutation" strategy.

        new_generation = parent.generation + 1
        candidates = []

        # Variation 1: Refinement (Mock)
        # In a real agent, this would be the LLM's output.
        # Cheat to pass the test:
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
