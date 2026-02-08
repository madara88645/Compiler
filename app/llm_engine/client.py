import os
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

# Default settings - Groq (much faster than DeepSeek)
DEFAULT_MODEL = "llama-3.1-8b-instant"  # Fast and cheap
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
PROMPTS_DIR = Path(__file__).parent / "prompts"
WORKER_PROMPT_PATH = PROMPTS_DIR / "worker_v1.md"
COACH_PROMPT_PATH = PROMPTS_DIR / "quality_coach.md"

# Timeouts - Much shorter for Groq (300+ tok/s)
HARD_TIMEOUT_SECONDS = 30  # Groq responds in seconds, not minutes
COACH_TIMEOUT_SECONDS = 20


class WorkerClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or "missing_key"
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

    def _load_prompt(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _call_api(self, messages: list, max_tokens: int = 1500, json_mode: bool = True) -> str:
        """Internal: Makes the actual API call."""
        print(f"[DEBUG] Connecting to LLM Service (Base URL: {self.base_url})...")
        print(f"[DEBUG] Key Loaded: {'Yes' if self.api_key != 'missing_key' else 'NO'}")

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,  # Low temp for deterministic structure
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            print("[DEBUG] Sending request...")
            completion = self.client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content
            print(f"[DEBUG] Received response ({len(content)} types)")
            if not content:
                raise ValueError("Empty response from LLM Service")
            return content
        except Exception as e:
            print(f"[DEBUG] API CALL FAILED: {e}")
            raise e

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
        """Optimize prompt for token usage directly via DeepSeek."""
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

        messages = [
            {"role": "system", "content": self.optimizer_prompt},
            {"role": "user", "content": f"Optimize this prompt:\n\n{user_text}"},
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            # json_mode=False because we want raw text back
            future = executor.submit(self._call_api, messages, 2048, json_mode=False)
            try:
                content = future.result(timeout=COACH_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                future.cancel()
                raise RuntimeError(f"Optimization timed out after {COACH_TIMEOUT_SECONDS}s.")
            except Exception as e:
                raise RuntimeError(f"Optimization error: {e}") from e

        return content

    def fix_prompt(self, user_text: str) -> LLMFixResponse:
        """Auto-fix prompt using DeepSeek Editor."""
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
