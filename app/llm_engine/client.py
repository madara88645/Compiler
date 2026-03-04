import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Load .env file if it exists (for API keys)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from openai import OpenAI, APIError
from .schemas import WorkerResponse, QualityReport, LLMFixResponse

# Default settings - Groq (much faster than LLM Service)
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
PROMPTS_DIR = Path(__file__).parent / "prompts"
WORKER_PROMPT_PATH = PROMPTS_DIR / "worker_v1.md"
COACH_PROMPT_PATH = PROMPTS_DIR / "quality_coach.md"
AGENT_GENERATOR_PROMPT_PATH = PROMPTS_DIR / "agent_generator.md"
SKILLS_GENERATOR_PROMPT_PATH = PROMPTS_DIR / "skills_generator.md"
MULTI_AGENT_PLANNER_PROMPT_PATH = PROMPTS_DIR / "multi_agent_planner.md"

# Timeouts - Much shorter for Groq (300+ tok/s)
# Allow overriding timeout via env var
try:
    HARD_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT", 30))
except ValueError:
    HARD_TIMEOUT_SECONDS = 30

COACH_TIMEOUT_SECONDS = 20


class WorkerClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or "missing_key"
        )
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
        self.model = model

        # Explicit timeout for the HTTP client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=HARD_TIMEOUT_SECONDS,  # Pass timeout to underlying httpx client
        )
        self.system_prompt = self._load_prompt(WORKER_PROMPT_PATH)
        self.coach_prompt = self._load_prompt(COACH_PROMPT_PATH)
        self.optimizer_prompt = self._load_prompt(PROMPTS_DIR / "optimizer.md")
        self.editor_prompt = self._load_prompt(PROMPTS_DIR / "editor.md")
        self.agent_generator_prompt = self._load_prompt(AGENT_GENERATOR_PROMPT_PATH)
        self.skills_generator_prompt = self._load_prompt(SKILLS_GENERATOR_PROMPT_PATH)
        self.multi_agent_planner_prompt = self._load_prompt(MULTI_AGENT_PLANNER_PROMPT_PATH)

    def _load_prompt(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _call_api(self, messages: list, max_tokens: int = 1500, json_mode: bool = True) -> str:
        """Internal: Makes the actual API call."""
        print(f"[DEBUG] Connecting to LLM Service (Base URL: {self.base_url})...", file=sys.stderr)
        print(
            f"[DEBUG] Key Loaded: {'Yes' if self.api_key != 'missing_key' else 'NO'}",
            file=sys.stderr,
        )

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,  # Low temp for deterministic structure
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            print("[DEBUG] Sending request...", file=sys.stderr)
            completion = self.client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content
            print(f"[DEBUG] Received response ({len(content)} types)", file=sys.stderr)
            if not content:
                raise ValueError("Empty response from LLM Service")
            return content
        except Exception as e:
            print(f"[DEBUG] API CALL FAILED: {e}", file=sys.stderr)
            raise e

    def _single_agent_prompt(self, include_example_code: bool) -> str:
        prompt = (
            self.agent_generator_prompt
            or "You are an Expert AI Agent Architect. Generate a comprehensive system prompt for an AI agent based on the user request. Output in Markdown."
        )
        if include_example_code:
            return prompt

        prompt = re.sub(
            r"\n## Example Code \(Pseudo-code Skeleton\).*?(?=\n## TONE & STYLE)",
            "",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(
            r"\n## OPTIONAL EXAMPLE CODE SECTION.*?(?=\n## INPUT HANDLING)",
            "",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(r"^- In Example Code:.*\n", "", prompt, flags=re.MULTILINE)
        prompt = re.sub(r"^- Keep code examples.*\n", "", prompt, flags=re.MULTILINE)
        prompt = re.sub(
            r"^- Only include an `## Example Code .*?$\n?",
            "",
            prompt,
            flags=re.MULTILINE,
        )
        prompt += (
            "\n\n## EXAMPLE CODE SETTING\n"
            "- Example code is disabled for this request.\n"
            "- Omit any `## Example Code` section from the final markdown.\n"
            "- Do not include fenced code blocks or pseudo-code unless the user explicitly asks for raw code."
        )
        return prompt

    def _multi_agent_prompt(self, include_example_code: bool) -> str:
        prompt = (
            self.multi_agent_planner_prompt
            or "You are an Expert AI Systems Architect. Decompose the task into 2-4 specialized agents. Output in Markdown."
        )
        if include_example_code:
            return prompt

        prompt = re.sub(
            r"\nAfter all agents, add a swarm-level pseudo-code skeleton:.*?(?=\n## RULES)",
            "",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(
            r"\n## OPTIONAL SWARM EXAMPLE CODE SECTION.*",
            "",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(
            r"^- Only include a final `## Swarm Example Code .*?$\n?",
            "",
            prompt,
            flags=re.MULTILINE,
        )
        prompt += (
            "\n\n## EXAMPLE CODE SETTING\n"
            "- Example code is disabled for this request.\n"
            "- Do not add a `## Swarm Example Code` section.\n"
            "- Do not include fenced code blocks or pseudo-code unless the user explicitly asks for raw code."
        )
        return prompt

    def _skill_prompt(self, include_example_code: bool) -> str:
        prompt = (
            self.skills_generator_prompt
            or "You are an Expert AI Skills Architect. Generate a comprehensive skill definition based on the user request. Output in Markdown."
        )
        if include_example_code:
            return prompt

        prompt = re.sub(
            r"\n## OPTIONAL IMPLEMENTATION EXAMPLE SECTION.*?(?=\n## INPUT HANDLING)",
            "",
            prompt,
            flags=re.DOTALL,
        )
        prompt = re.sub(
            r"^- Only include an implementation example section.*\n",
            "",
            prompt,
            flags=re.MULTILINE,
        )
        prompt += (
            "\n\n## EXAMPLE CODE SETTING\n"
            "- Example code is disabled for this request.\n"
            "- Omit any `## Implementation Example` section from the final markdown.\n"
            "- Keep `## Implementation` as a concise, code-free execution plan.\n"
            "- Do not include fenced code blocks or pseudo-code unless the user explicitly asks for raw code."
        )
        return prompt

    def process(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> WorkerResponse:
        """Compile user text into structured prompt components."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_text},
        ]

        if context:
            ctx_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            messages.insert(1, {"role": "system", "content": f"Context:\n{ctx_str}"})

        with ThreadPoolExecutor(max_workers=3) as executor:
            # Increased max tokens to prevent JSON truncation (reliability > speed cap)
            future = executor.submit(self._call_api, messages, max_tokens=3000)
            try:
                content = future.result(timeout=HARD_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(
                    f"LLM API did not respond within {HARD_TIMEOUT_SECONDS} seconds."
                )
            except APIError as e:
                raise RuntimeError(f"LLM API failed: {e}") from e
            except Exception as e:
                raise RuntimeError(f"LLM error: {e}") from e

        response = WorkerResponse.model_validate_json(content)

        # Auto-construct optimized_content (Expanded Prompt) if missing
        # This saves the LLM from generating redundant text
        if not response.optimized_content or len(response.optimized_content) < 50:
            parts = []
            if response.system_prompt:
                parts.append(response.system_prompt)
            if response.user_prompt:
                parts.append(response.user_prompt)
            if response.plan:
                parts.append(response.plan)
            response.optimized_content = "\n\n---\n\n".join(parts)

        return response

    def analyze_prompt(self, user_text: str) -> QualityReport:
        """Analyze prompt quality and return score/feedback."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")

        if not self.coach_prompt:
            raise RuntimeError("Quality Coach prompt not found.")

        messages = [
            {"role": "system", "content": self.coach_prompt},
            {"role": "user", "content": f"Analyze this prompt:\n\n{user_text}"},
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            future = executor.submit(self._call_api, messages, 1024)
            try:
                content = future.result(timeout=COACH_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Quality analysis timed out after {COACH_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Quality analysis error: {e}") from e

        return QualityReport.model_validate_json(content)

    def optimize_prompt(self, user_text: str, max_tokens: int = None, max_chars: int = None) -> str:
        """Optimize prompt for token usage directly via Worker LLM."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")

        if not self.optimizer_prompt:
            # Fallback if file missing
            self.optimizer_prompt = "You are a specialized Prompt Optimizer. Your goal is to reduce token usage by at least 20% while preserving the exact intent, core constraints, and variables. Remove fluff, conversational filler, and redundancy. Return ONLY the optimized prompt text."

        # Dynamically append constraints
        sys_prompt = self.optimizer_prompt
        constraints = []
        if max_tokens:
            constraints.append(f"TARGET: Strict maximum of {max_tokens} tokens.")
        if max_chars:
            constraints.append(f"TARGET: Strict maximum of {max_chars} characters.")

        if constraints:
            sys_prompt += "\n\n" + "\n".join(constraints)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Optimize this prompt:\n\n{user_text}"},
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            future = executor.submit(
                self._call_api, messages, 2048, json_mode=False
            )  # Optimizer output is text not JSON
            try:
                content = future.result(timeout=COACH_TIMEOUT_SECONDS)
                return content.strip()
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Optimization timed out after {COACH_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Optimization error: {e}") from e

    def fix_prompt(self, user_text: str) -> LLMFixResponse:
        """Auto-fix prompt using LLM Editor."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")

        if not self.editor_prompt:
            self.editor_prompt = "You are an expert editor. Rewrite this prompt to be better. Return JSON: {fixed_text, explanation, changes}"

        messages = [
            {"role": "system", "content": self.editor_prompt},
            {"role": "user", "content": f"Fix this prompt:\n\n{user_text}"},
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            future = executor.submit(self._call_api, messages, 1500)
            try:
                content = future.result(timeout=COACH_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Auto-fix timed out after {COACH_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Auto-fix error: {e}") from e

        return LLMFixResponse.model_validate_json(content)

    def expand_query_intent(self, user_text: str) -> Dict[str, Any]:
        """Expand user query into semantic search terms."""
        if self.api_key == "missing_key":
            return {"queries": [user_text]}

        prompt_path = PROMPTS_DIR / "query_expansion.md"
        if not prompt_path.exists():
            return {"queries": [user_text]}

        system_prompt = prompt_path.read_text(encoding="utf-8")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._call_api, messages, 500, json_mode=True)
                content = future.result(timeout=10)  # Fast timeout for query expansion
                import json

                return json.loads(content)
        except Exception as e:
            print(f"[WorkerClient] Query expansion failed: {e}")
            return {"queries": [user_text]}

    def generate_agent(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
        multi_agent: bool = False,
        include_example_code: bool = False,
    ) -> str:
        """Generate a comprehensive AI Agent system prompt."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")

        if multi_agent:
            system_prompt = self._multi_agent_prompt(include_example_code)
        else:
            system_prompt = self._single_agent_prompt(include_example_code)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        # Changed: add anti-hallucination guidance so generated examples stay honest when API/library details are unknown.
        safety_note = (
            "Reliability requirements for generated markdown:\n"
            "- Do not invent dependencies, SDKs, or helper libraries that are not explicitly provided in context.\n"
            "- Do not invent API fields, endpoints, or write operations unless their exact shape is known from context.\n"
            "- If implementation details are unknown, use pseudo-code with TODO comments instead of pretending certainty.\n"
            "- Keep the system prompt high-level and practical, and keep the example interaction short and natural."
        )
        if multi_agent:
            example_code_note = (
                "Include a final `## Swarm Example Code (Pseudo-code Skeleton)` section with concise pseudo-code only when it reduces ambiguity."
                if include_example_code
                else (
                    "Do not include any example code snippets, pseudo-code, or fenced code blocks. "
                    "Omit the entire `## Swarm Example Code (Pseudo-code Skeleton)` section from the generated output."
                )
            )
        else:
            example_code_note = (
                "Include a final `## Example Code (Pseudo-code Skeleton)` section with concise pseudo-code only when it reduces ambiguity."
                if include_example_code
                else (
                    "Do not include any example code snippets, pseudo-code, or fenced code blocks. "
                    "Omit the entire `## Example Code (Pseudo-code Skeleton)` section from the generated output."
                )
            )
        messages.insert(1, {"role": "system", "content": safety_note})
        messages.insert(2, {"role": "system", "content": example_code_note})

        if context:
            ctx_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            messages.insert(3, {"role": "system", "content": f"Context:\n{ctx_str}"})

        with ThreadPoolExecutor(max_workers=3) as executor:
            # json_mode=False because we want Markdown text back
            future = executor.submit(self._call_api, messages, 3000, json_mode=False)
            try:
                content = future.result(timeout=HARD_TIMEOUT_SECONDS)
                if multi_agent:
                    import logging
                    import re

                    # Count top-level agent headers: lines matching "# Agent N:" or "# Agent N "
                    agent_headers = re.findall(
                        r"^#\s+Agent\s+\d+", content, re.MULTILINE | re.IGNORECASE
                    )
                    agent_count = len(agent_headers)
                    if agent_count > 4:
                        logging.warning(
                            f"[AgentGenerator] Multi-agent output exceeded limit: "
                            f"{agent_count} agents detected (max 4). "
                            f"Consider strengthening the multi_agent_planner prompt."
                        )
                    elif agent_count == 0:
                        logging.warning(
                            "[AgentGenerator] Multi-agent output contains no '# Agent N:' headers. "
                            "Output may be malformed."
                        )
                return content
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Agent generation timed out after {HARD_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Agent generation error: {e}") from e

    def generate_skill(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
        include_example_code: bool = False,
    ) -> str:
        """Generate a comprehensive AI Skill definition."""
        if self.api_key == "missing_key":
            raise RuntimeError("API Key is missing. Please set OPENAI_API_KEY.")
        system_prompt = self._skill_prompt(include_example_code)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

        safety_note = (
            "Reliability requirements for generated markdown:\n"
            "- Do not invent dependencies, SDKs, helpers, or API fields that are not known from context.\n"
            "- If implementation details are unknown, provide explicit TODO-oriented steps instead of fake certainty.\n"
            "- Keep the skill definition practical, modular, and implementation-ready."
        )
        example_code_note = (
            "Include a final `## Implementation Example` section with concise code only when explicitly requested."
            if include_example_code
            else (
                "Do not include any example code snippets, pseudo-code, or fenced code blocks. "
                "Omit the entire `## Implementation Example` section from the generated output."
            )
        )
        messages.insert(1, {"role": "system", "content": safety_note})
        messages.insert(2, {"role": "system", "content": example_code_note})

        if context:
            ctx_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
            messages.insert(3, {"role": "system", "content": f"Context:\n{ctx_str}"})

        with ThreadPoolExecutor(max_workers=3) as executor:
            # json_mode=False because we want Markdown text back
            future = executor.submit(self._call_api, messages, 3000, json_mode=False)
            try:
                content = future.result(timeout=HARD_TIMEOUT_SECONDS)
                return content
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Skill generation timed out after {HARD_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Skill generation error: {e}") from e
