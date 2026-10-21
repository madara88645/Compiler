"""Exact model ids from OpenRouter's 2026-10-19 retirement notice.

This policy applies only to OpenRouter requests, including BYOK. It says
nothing about the availability of a model on a direct OpenAI endpoint.
"""

from __future__ import annotations

from datetime import date
import logging
from urllib.parse import urlparse

RETIREMENT_DATE = date(2027, 1, 14)
RETIRING_MODEL_IDS = frozenset(
    {
        "openai/gpt-4o",
        "openai/gpt-4o-2024-05-13",
        "openai/gpt-4o-2024-08-06",
        "openai/gpt-4o-2024-11-20",
        "openai/gpt-4o-mini",
        "openai/gpt-4o-mini-2024-07-18",
        "openai/gpt-4.1",
        "openai/gpt-4.1-mini",
    }
)
# Only known legacy spellings; never guess arbitrary model families or suffixes.
_RETIRING_SHORT_IDS = {model.removeprefix("openai/"): model for model in RETIRING_MODEL_IDS}


def is_openrouter_url(base_url: str) -> bool:
    return urlparse(str(base_url)).hostname == "openrouter.ai"


def retiring_model_id(model: str) -> str | None:
    model = (model or "").strip()
    canonical = _RETIRING_SHORT_IDS.get(model, model)
    return canonical if canonical in RETIRING_MODEL_IDS else None


def retirement_warning(model: str) -> str | None:
    canonical = retiring_model_id(model)
    if canonical is None:
        return None
    return (
        f"OpenRouter model '{canonical}' retires on {RETIREMENT_DATE.isoformat()}, including BYOK. "
        "Choose a supported model explicitly (for example openai/gpt-oss-20b); "
        "old cost estimates retain the original model's rates."
    )


def prepare_openrouter_model(model: str, *, today: date | None = None) -> str:
    """Keep explicit legacy choices until retirement; never silently switch a paid model."""
    canonical = retiring_model_id(model)
    if canonical is None:
        return model
    warning = retirement_warning(model)
    if (today or date.today()) >= RETIREMENT_DATE:
        raise ValueError(warning)
    logging.getLogger(__name__).warning(warning)
    return canonical
