from __future__ import annotations

from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from api.main import app
from app.optimizer.fidelity import apply_fidelity_guard
from app.optimizer.language_costs import estimate_prompt_cost
from app.optimizer.model_catalog import get_model_metadata
from app.text_utils import estimate_tokens


def test_live_reviewed_catalog_has_current_model_metadata() -> None:
    deepseek = get_model_metadata("deepseek/deepseek-v4.1-flash")
    luna = get_model_metadata("openai/gpt-5.6-luna")

    assert deepseek is not None
    assert deepseek.tokenizer == "DeepSeek"
    assert deepseek.input_rate_per_million == 0.15
    assert deepseek.output_rate_per_million == 0.60
    assert luna is not None
    assert luna.context_length == 1_050_000
    assert luna.input_rate_per_million == 0.20


def test_non_gpt_estimate_identifies_heuristic_tokenizer() -> None:
    estimate = estimate_prompt_cost(
        "Use the API and preserve {{project_id}}.",
        model="deepseek/deepseek-v4.1-flash",
    )

    assert estimate.tokenizer_name == "DeepSeek"
    assert estimate.tokenizer_method.startswith("heuristic:")
    assert estimate.tokenizer_method.endswith(":estimated")
    assert estimate.token_count_is_estimate is True
    assert estimate.pricing_known is True


def test_unknown_pricing_is_unavailable_instead_of_free() -> None:
    estimate = estimate_prompt_cost("hello", model="provider/model-that-is-not-verified")

    assert estimate.estimated_cost_usd == 0.0  # backwards-compatible numeric field
    assert estimate.pricing_known is False
    assert any("unavailable" in warning.lower() for warning in estimate.warnings)


def test_no_whitespace_text_does_not_collapse_to_two_tokens() -> None:
    assert estimate_tokens("界" * 120) >= 30


def test_fidelity_guard_restores_source_when_literal_code_or_url_is_dropped() -> None:
    source = "Call https://example.com/search and keep {{query}}.\n\n```python\nreturn query\n```\n"
    guarded, warnings = apply_fidelity_guard(source, "Call the endpoint.")

    assert guarded == source
    assert any("fenced code block" in warning for warning in warnings)
    assert any("URL" in warning or "placeholder" in warning for warning in warnings)


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_local_api_path_does_not_call_cloud_worker(mock_optimize) -> None:
    client = TestClient(app)

    response = client.post(
        "/optimize",
        json={"text": "Please  write  a plan.", "provider": "local", "model": "offline"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    mock_optimize.assert_not_called()
    assert data["optimizer_provider"] == "local"
    assert data["optimizer_model"] == "offline"
    assert data["optimizer_call_usage"] is None
    assert any("no cloud LLM call" in warning for warning in data["warnings"])


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_reported_usage_cost_is_distinct_from_catalog_estimate(mock_optimize) -> None:
    mock_optimize.return_value = (
        "Write a plan.",
        {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.123456},
    )
    client = TestClient(app)

    response = client.post("/optimize", json={"text": "Write a very verbose plan."})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["actual_input_tokens"] == 100
    assert data["actual_output_tokens"] == 20
    assert data["actual_cost_usd"] == 0.123456
    assert data["estimated_actual_cost_usd"] is not None
    assert data["optimizer_provider"] == "openrouter"


@patch("app.llm_engine.client.WorkerClient.optimize_prompt")
def test_unsupported_provider_is_rejected_before_cloud_call(mock_optimize) -> None:
    response = TestClient(app).post(
        "/optimize", json={"text": "Write a plan.", "provider": "anthropic"}
    )
    assert response.status_code == 422
    mock_optimize.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        "src/my-file.test.ts",
        "./src/main.py",
        "../../src/main.py",
        "/app/src/main.py",
        "~/src/main.py",
    ],
)
def test_fidelity_retains_relative_absolute_and_home_paths(path: str) -> None:
    source = f"Carefully update {path} while preserving existing behavior."
    candidate = f"Update {path}; preserve behavior."
    assert apply_fidelity_guard(source, candidate) == (candidate, [])
    guarded, warnings = apply_fidelity_guard(source, "Update the file.")
    assert guarded == source
    assert any("file path" in warning for warning in warnings)


def test_fidelity_does_not_treat_long_separator_as_a_file_path() -> None:
    source = "Review this section\n" + "-" * 100_000 + "\nKeep src/main.py intact."
    candidate = "Review this section. Keep src/main.py intact."
    assert apply_fidelity_guard(source, candidate) == (candidate, [])
