from __future__ import annotations
import json
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel

from app.llm_engine.client import WorkerClient


class CriticIssue(BaseModel):
    type: str
    description: str
    severity: str


class CriticVerdict(BaseModel):
    verdict: str
    score: int
    issues: List[CriticIssue]
    feedback: Optional[str] = None


class CriticAgent:
    """
    Agent 7: The Critic.
    Reviews prompts and code against trusted context to prevent hallucinations and errors.
    """

    def __init__(self, client: Optional[WorkerClient] = None):
        self.client = client or WorkerClient()
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load the critic system prompt from disk."""
        # Assuming typical structure relative to this file
        # app/optimizer/critic.py -> app/llm_engine/prompts/critic.md
        base_path = Path(__file__).parent.parent / "llm_engine" / "prompts" / "critic.md"
        try:
            with open(base_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # Fallback for testing/dev if file missing
            return "You are a Critic. Verify the following inputs against the provided context (code or knowledge)."

    def critique(
        self,
        user_request: str,
        system_prompt: str,
        generated_code: str = "",
        context: str = "",
    ) -> CriticVerdict:
        """
        Run the critique loop.
        """
        # Prepare inputs
        prompt = self.prompt_template.replace("{{user_request}}", user_request)
        prompt = prompt.replace("{{system_prompt}}", system_prompt)
        prompt = prompt.replace("{{generated_code}}", generated_code)
        prompt = prompt.replace("{{context}}", context)

        messages = [
            {"role": "system", "content": "You are a strict code reviewer and QA agent."},
            {"role": "user", "content": prompt},
        ]

        # Call LLM
        # Force JSON mode for structured output
        try:
            response_text = self.client._call_api(messages, max_tokens=1000, json_mode=True)
            data = json.loads(response_text)
            return CriticVerdict(**data)
        except Exception as e:
            # Fallback in case of parsing error or LLM failure
            return CriticVerdict(
                verdict="REJECT",
                score=0,
                issues=[
                    CriticIssue(
                        type="System Error",
                        description=f"Critic failed to execute: {str(e)}",
                        severity="critical",
                    )
                ],
                feedback="System error during critique.",
            )
