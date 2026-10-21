"""Offline migration checks; all provider/SDK calls are mocked."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.llm.base import ProviderConfig
from app.llm.openrouter_models import (
    RETIRING_MODEL_IDS,
    is_openrouter_url,
    prepare_openrouter_model,
    retirement_warning,
)
from app.llm.providers import OpenAIProvider
from app.llm_engine.client import WorkerClient
from app.optimizer.models import OptimizationConfig, OptimizationRun
from app.optimizer.language_costs import estimate_prompt_cost
from app.optimizer.estimator import estimate_run_cost
from app.optimizer.costs import PricingModel


@pytest.mark.parametrize("model", sorted(RETIRING_MODEL_IDS))
def test_exact_ids_and_legacy_short_forms_warn_before_retirement(model, caplog):
    for spelling in [model, model.removeprefix("openai/")]:
        assert prepare_openrouter_model(spelling, today=date(2027, 1, 13)) == model
        assert "2027-01-14" in caplog.text
        assert "BYOK" in caplog.text
        assert "secret" not in caplog.text
        for day in [date(2027, 1, 14), date(2027, 1, 15)]:
            with pytest.raises(ValueError, match="Choose a supported model explicitly"):
                prepare_openrouter_model(spelling, today=day)


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "custom/model", "openai/gpt-4o-custom"])
def test_other_choices_are_preserved(model):
    assert prepare_openrouter_model(model, today=date(2028, 1, 1)) == model
    assert retirement_warning(model) is None


def test_old_saved_runs_and_prices_remain_readable_without_becoming_replacement_prices():
    for spelling in ["gpt-4o-mini", "openai/gpt-4o-mini"]:
        run = OptimizationRun.model_validate({"config": {"model": spelling}, "generations": []})
        assert run.config.model == spelling
        estimate = estimate_prompt_cost("hello", model=spelling, token_count_override=1_000_000)
        assert estimate.pricing_known is True
        assert estimate.estimated_cost_usd == pytest.approx(0.15)
        assert estimate.output_rate_per_million == pytest.approx(0.60)
        assert "2027-01-14" in estimate.warnings[0]
        assert PricingModel.get_rate(spelling) == (0.15, 0.60)
        run_estimate = estimate_run_cost(run.config, "hello")
        assert run_estimate["cost_estimate_available"] is True
        assert "2027-01-14" in run_estimate["message"]
    # Dated variants have no reviewed pricing record: never borrow the alias rate.
    estimate = estimate_prompt_cost("hello", model="openai/gpt-4o-2024-05-13")
    assert estimate.pricing_known is False
    assert any("2027-01-14" in warning for warning in estimate.warnings)
    assert PricingModel.get_rate("openai/gpt-4o-2024-05-13") == (0.0, 0.0)


def test_defaults_match_existing_cloud_default():
    assert ProviderConfig().model == OptimizationConfig().model == "openai/gpt-oss-20b"


@pytest.mark.parametrize(
    "base_url,is_router",
    [
        ("https://openrouter.ai/api/v1", True),
        ("https://api.openai.com/v1", False),
        ("https://openrouter.ai.example.com/v1", False),
        ("https://example.com/openrouter.ai/v1", False),
    ],
)
def test_provider_policy_is_scoped_to_openrouter_host(base_url, is_router):
    assert is_openrouter_url(base_url) is is_router
    provider = OpenAIProvider(ProviderConfig(api_key="fake", base_url=base_url, model="gpt-4o"))
    reply = MagicMock()
    reply.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    try:
        with patch(
            "app.llm.providers.prepare_openrouter_model", return_value="openai/gpt-4o"
        ) as prepare:
            with patch.object(provider.client, "post", return_value=reply) as post:
                assert provider.generate("hello").content == "ok"
                assert prepare.called is is_router
                assert post.call_args.kwargs["json"]["model"] == (
                    "openai/gpt-4o" if is_router else "gpt-4o"
                )
    finally:
        provider.close()


def test_retired_provider_request_has_actionable_error_and_never_posts():
    provider = OpenAIProvider(ProviderConfig(api_key="fake", model="gpt-4o"))
    try:
        with patch(
            "app.llm.providers.prepare_openrouter_model",
            side_effect=ValueError("Choose a supported model explicitly"),
        ):
            with patch.object(provider.client, "post") as post:
                result = provider.generate("hello")
                post.assert_not_called()
                assert result.content == "Error: Choose a supported model explicitly"
    finally:
        provider.close()


@pytest.mark.parametrize(
    "base_url,is_router",
    [
        ("https://openrouter.ai/api/v1", True),
        ("https://api.openai.com/v1", False),
    ],
)
def test_worker_checks_effective_model_override_only_for_openrouter(base_url, is_router):
    with patch("app.llm_engine.client.OpenAI") as sdk:
        sdk.return_value.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="{}"), finish_reason="stop")],
            usage=None,
        )
        worker = WorkerClient(api_key="fake", base_url=base_url, model="openai/gpt-oss-20b")
        with patch(
            "app.llm_engine.client.prepare_openrouter_model", return_value="openai/gpt-4o-mini"
        ) as prepare:
            worker._call_api([], model_override="gpt-4o-mini")
            assert prepare.called is is_router
            if is_router:
                prepare.assert_called_once_with("gpt-4o-mini")
            call = sdk.return_value.chat.completions.create.call_args.kwargs
            assert call["model"] == ("openai/gpt-4o-mini" if is_router else "gpt-4o-mini")
        if is_router:
            sdk.return_value.chat.completions.create.reset_mock()
            with patch(
                "app.llm_engine.client.prepare_openrouter_model", side_effect=ValueError("retired")
            ):
                with pytest.raises(ValueError, match="retired"):
                    worker._call_api([])
                sdk.return_value.chat.completions.create.assert_not_called()
