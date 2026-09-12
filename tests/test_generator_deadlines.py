import asyncio
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.routes.generators import (
    AgentGenRequest,
    SkillGenRequest,
    generate_agent_endpoint,
    generate_skill_endpoint,
)
from app.llm_engine.client import WorkerClient


@pytest.mark.parametrize("method", ["generate_agent", "generate_skill"])
def test_generation_can_finish_after_the_short_compiler_deadline(method):
    with patch("app.llm_engine.client.OpenAI"):
        client = WorkerClient(api_key="test")

    def slower_generation(*args, **kwargs):
        time.sleep(0.06)
        return "# Generated instructions"

    with (
        patch("app.llm_engine.client.HARD_TIMEOUT_SECONDS", 0.01),
        patch("app.llm_engine.client.GENERATOR_TIMEOUT_SECONDS", 0.5, create=True),
        patch.object(client, "_call_api", side_effect=slower_generation),
    ):
        assert getattr(client, method)("Describe a support agent") == "# Generated instructions"


def test_transport_receives_the_call_deadline_and_does_not_retry_after_it():
    with patch("app.llm_engine.client.OpenAI") as factory:
        factory.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="# Agent"))], usage=None
        )
        client = WorkerClient(api_key="test")
        client._call_api_with_timeout([], max_tokens=100, timeout_seconds=90, json_mode=False)
        assert factory.return_value.chat.completions.create.call_args.kwargs["timeout"] == 90
        assert factory.call_args.kwargs["max_retries"] == 0


@pytest.mark.parametrize("kind", ["agent", "skill"])
def test_synchronous_generation_does_not_block_other_async_work(kind):
    order = []

    def generate(*args, **kwargs):
        time.sleep(0.06)
        order.append("generated")
        return "# Generated instructions"

    compiler = MagicMock()
    getattr(compiler, f"generate_{kind}").side_effect = generate

    async def check():
        async def tick():
            await asyncio.sleep(0.01)
            order.append("tick")

        request = (
            AgentGenRequest(description="Support agent")
            if kind == "agent"
            else SkillGenRequest(description="Support skill")
        )
        endpoint = generate_agent_endpoint if kind == "agent" else generate_skill_endpoint
        await asyncio.gather(endpoint(request), tick())

    with patch("api.routes.generators._get_compiler", return_value=compiler):
        asyncio.run(check())
    assert order == ["tick", "generated"]
