"""Live integration tests for the /optimize endpoint against the real Groq API.

These tests are double-gated:
- The `live` pytest marker is skipped by default unless `--run-live` or
  `PROMPTC_RUN_LIVE_TESTS=1` is set, so CI does not hit Groq accidentally.
- The `GROQ_API_KEY` skipif keeps local runs from emitting confusing auth errors.

Run them explicitly with:

    GROQ_API_KEY=... python -m pytest tests/optimizer/test_optimize_live.py --run-live -m live -v

Assertions verify *invariants* (language preserved, no wrapper text, costs > 0)
rather than exact strings, since real LLM output is non-deterministic.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.optimizer.language_costs import detect_language

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("GROQ_API_KEY") and not os.environ.get("OPENAI_API_KEY"),
        reason="GROQ_API_KEY/OPENAI_API_KEY not set; skipping live Groq tests",
    ),
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _post_optimize(client: TestClient, text: str, **extra) -> dict:
    response = client.post("/optimize", json={"text": text, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_live_turkish_diacritic_input_stays_turkish(client: TestClient) -> None:
    """A Turkish prompt with diacritics should produce Turkish output and a populated EN variant."""

    text = (
        "Lütfen bana bir Python fonksiyonu yaz. Bu fonksiyon kullanıcıdan bir e-posta "
        "adresi almalı, geçerli olup olmadığını kontrol etmeli ve sonucu döndürmeli. "
        "Güvenlik kısıtlarını koru ve {{user_level}} değişkenini kullan."
    )
    data = _post_optimize(client, text)

    assert data["source_language"] == "tr"
    assert (
        detect_language(data["text"]) == "tr"
    ), f"Expected Turkish output but got: {data['text']!r}"
    assert "{{user_level}}" in data["text"], "Placeholder must survive optimization"
    assert data["english_variant"], "English compact variant should be populated for TR input"
    assert data["english_variant_tokens"] > 0
    assert data["english_variant_cost_usd"] > 0
    drift_warnings = [w for w in data["warnings"] if "language differs" in w.lower()]
    assert not drift_warnings, f"Should not warn about language drift: {drift_warnings}"


def test_live_turkish_diacritic_free_input_is_detected_as_turkish(client: TestClient) -> None:
    """Diacritic-free Turkish should still be detected as TR via keyword scoring."""

    text = (
        "Bu fonksiyon icin guvenlik kisitlari yaz. Junior gelistirici icin uygulama plani olustur."
    )
    data = _post_optimize(client, text)

    assert data["source_language"] == "tr"
    assert data["english_variant"], "English compact variant should be populated for TR input"


def test_live_english_input_hides_english_variant(client: TestClient) -> None:
    """English input should be detected as EN; the EN variant panel is irrelevant."""

    text = (
        "Please write a Python function that validates email addresses and returns "
        "a boolean. Handle edge cases gracefully."
    )
    data = _post_optimize(client, text)

    assert data["source_language"] == "en"
    assert detect_language(data["text"]) == "en"
    drift_warnings = [w for w in data["warnings"] if "language differs" in w.lower()]
    assert not drift_warnings


def test_live_optimizer_strips_wrapper_labels_if_emitted(client: TestClient) -> None:
    """Even if the LLM emits a wrapper label, post-processing must strip it."""

    text = (
        "I would like you to please act as a senior marketing expert and write a "
        "professional yet exciting LinkedIn post about our brand new AI-powered coffee "
        "machine. Include exactly 3 hashtags."
    )
    data = _post_optimize(client, text)

    assert "**Optimized Prompt**" not in data["text"]
    assert not data["text"].lower().startswith("optimized prompt:")
    assert not data["text"].lower().startswith("output:")
    assert not data["text"].lower().startswith("result:")


def test_live_costs_and_metadata_are_populated(client: TestClient) -> None:
    """Sanity-check the response shape against the real Groq pricing path."""

    text = "Write a haiku about debugging at 3am."
    data = _post_optimize(client, text)

    assert data["provider"] == "groq"
    assert data["model"], "Model identifier should be present"
    assert data["before_tokens"] > 0
    assert data["after_tokens"] > 0
    assert data["estimated_input_cost_usd"] >= 0
    assert data["estimated_output_cost_usd"] >= 0
    assert data["tokenizer_method"].endswith(":estimated")
