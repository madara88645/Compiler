from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import List, Optional, Union
from .models import Candidate
from app.llm.base import LLMProvider


class MutationStrategy(ABC):
    """Base class for mutation strategies."""

    SYSTEM_PROMPT = ""
    NAME = "base"

    @abstractmethod
    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> Union[Candidate, str]:
        pass


class CompressorStrategy(MutationStrategy):
    NAME = "compressor"
    SYSTEM_PROMPT = """You are a token optimization expert.
Task: Rewrite the following prompt to be as concise as possible while retaining all instructions.
Return JSON: { "type": "compressed", "prompt": "..." }
"""

    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> str:
        if not provider:
            return "Short: " + parent.prompt_text[:50]

        try:
            response = provider.generate(
                f"Prompt:\n{parent.prompt_text}", system_prompt=self.SYSTEM_PROMPT
            )
            data = json.loads(response.content)
            return data.get("prompt", parent.prompt_text)
        except Exception:
            return parent.prompt_text


class CoTStrategy(MutationStrategy):
    NAME = "chain_of_thought"
    SYSTEM_PROMPT = """You are an AI optimization expert.
Task: Rewrite the prompt to encourage Chain-of-Thought reasoning (e.g., 'Let's think step by step').
Return JSON: { "type": "smart_cot", "prompt": "..." }
"""

    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> str:
        if not provider:
            return parent.prompt_text + "\nLet's think step by step."

        try:
            response = provider.generate(
                f"Prompt:\n{parent.prompt_text}", system_prompt=self.SYSTEM_PROMPT
            )
            data = json.loads(response.content)
            return data.get("prompt", parent.prompt_text)
        except Exception:
            return parent.prompt_text


class PersonaStrategy(MutationStrategy):
    NAME = "persona"
    SYSTEM_PROMPT = """You are an Expert Persona Designer.
Task: Rewrite the prompt to adopt a specific, relevant expert persona to improve quality.
Return JSON: { "type": "smart_persona", "prompt": "..." }
"""

    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> str:
        if not provider:
            return "You are an Expert.\n" + parent.prompt_text

        try:
            response = provider.generate(
                f"Prompt:\n{parent.prompt_text}", system_prompt=self.SYSTEM_PROMPT
            )
            data = json.loads(response.content)
            return data.get("prompt", parent.prompt_text)
        except Exception:
            return parent.prompt_text


class RefinementStrategy(MutationStrategy):
    NAME = "refinement"
    SYSTEM_PROMPT = "Refine..."

    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> str:
        if not provider:
            return parent.prompt_text + "\n(Refined to fix failures)"
        return parent.prompt_text


# Director Mode Constants
DIRECTOR_TEMPLATE = """You are an AI Prompt Editor.
Original Prompt: {{ prompt }}
User Instruction: {{ feedback }}
Task: Rewrite the prompt to strictly follow the user's instruction while keeping its original strengths."""


class DirectorStrategy(MutationStrategy):
    NAME = "director"
    SYSTEM_PROMPT = "You are an AI Prompt Editor. Follow user instructions to modify the prompt."

    # Note: DirectorStrategy is usually called explicitly with feedback, not via the standard loop.
    # But we implement mutate for consistency/fallback.
    def mutate(
        self, parent: Candidate, provider: Optional[LLMProvider], failures: List[str] = None
    ) -> str:
        # Without explicit feedback, we can't do much.
        return parent.prompt_text


STRATEGY_REGISTRY = {
    "compressor": CompressorStrategy(),
    "chain_of_thought": CoTStrategy(),
    "persona": PersonaStrategy(),
    "refinement": RefinementStrategy(),
    "director": DirectorStrategy(),
}


def get_strategy(name: str) -> MutationStrategy:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}")
    return STRATEGY_REGISTRY[name]
