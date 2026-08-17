import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from concurrent.futures import TimeoutError as FuturesTimeoutError
from openai import APIError

from app.llm_engine.client import WorkerClient, _sanitize_skill_definition_plain


def test_worker_client_prefers_openrouter_env_defaults():
    with patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_MODEL": "openai/gpt-oss-20b",
            "OPENROUTER_HTTP_REFERER": "https://prcompiler.com",
            "OPENROUTER_TITLE": "Prompt Compiler",
        },
        clear=False,
    ), patch("app.llm_engine.client.OpenAI") as mock_openai:
        client = WorkerClient()

    assert client.api_key == "or-key"
    assert client.base_url == "https://openrouter.ai/api/v1"
    assert client.model == "openai/gpt-oss-20b"
    mock_openai.assert_called_once()
    _, kwargs = mock_openai.call_args
    assert kwargs["default_headers"]["HTTP-Referer"] == "https://prcompiler.com"
    assert kwargs["default_headers"]["X-Title"] == "Prompt Compiler"


def test_call_api_requires_parameter_support_for_openrouter_json_mode():
    with patch("app.llm_engine.client.OpenAI") as mock_openai:
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
            usage=None,
        )
        create_mock = MagicMock(return_value=completion)
        mock_openai.return_value = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )
        client = WorkerClient(
            api_key="or-key",
            base_url="https://openrouter.ai/api/v1",
            model="openai/gpt-oss-20b",
        )

        response = client._call_api([{"role": "user", "content": "hello"}], json_mode=True)

    assert response == '{"ok":true}'
    _, kwargs = create_mock.call_args
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"]["provider"]["require_parameters"] is True


def test_worker_client_load_prompt(tmp_path):
    client = WorkerClient(api_key="key")
    # Existing path
    test_file = tmp_path / "test.md"
    test_file.write_text("hello prompt", encoding="utf-8")
    assert client._load_prompt(test_file) == "hello prompt"

    # Non-existing path
    assert client._load_prompt(tmp_path / "non_existing.md") == ""


def test_worker_client_resolve_mode():
    client = WorkerClient(api_key="key")
    assert client._resolve_mode("default") == "default"
    assert client._resolve_mode("conservative") == "conservative"
    assert client._resolve_mode("invalid") == "conservative"
    assert client._resolve_mode(None) == "conservative"


def test_worker_client_is_openrouter_request():
    client = WorkerClient(api_key="key", base_url="https://openrouter.ai/api/v1")
    assert client._is_openrouter_request() is True

    client2 = WorkerClient(api_key="key", base_url="https://api.openai.com/v1")
    assert client2._is_openrouter_request() is False


def test_worker_client_system_prompt_for_mode():
    client = WorkerClient(api_key="key")
    client.system_prompt = "system"
    client.system_prompt_conservative = "conservative"

    assert client._worker_system_prompt_for_mode("default") == "system"
    assert client._worker_system_prompt_for_mode("conservative") == "conservative"

    client.system_prompt_conservative = ""
    assert client._worker_system_prompt_for_mode("conservative") == "system"


def test_worker_client_call_api_with_timeout():
    with patch("app.llm_engine.client.OpenAI") as mock_openai:
        client = WorkerClient(api_key="key")

        # Mock success
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="llm response"))],
            usage=None,
        )
        mock_openai.return_value.chat.completions.create.return_value = completion

        res = client._call_api_with_timeout(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
            timeout_seconds=5,
        )
        assert res == "llm response"


def test_worker_client_call_api_with_timeout_timed_out():
    client = WorkerClient(api_key="key")

    from concurrent.futures import Future

    future = Future()
    future.set_exception(FuturesTimeoutError("Timed out"))

    with patch("concurrent.futures.ThreadPoolExecutor.submit", return_value=future):
        with pytest.raises(FuturesTimeoutError):
            client._call_api_with_timeout(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=100,
                timeout_seconds=1,
            )


def test_worker_client_call_api_usage_sink():
    with patch("app.llm_engine.client.OpenAI") as mock_openai:
        # Mock usage object as pydantic model style (with model_dump)
        usage_model = SimpleNamespace(model_dump=lambda: {"total_tokens": 50})
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="response"))],
            usage=usage_model,
        )
        mock_openai.return_value.chat.completions.create.return_value = completion

        client = WorkerClient(api_key="key")
        usage_sink = {}
        client._call_api([{"role": "user"}], usage_sink=usage_sink)
        assert usage_sink == {"total_tokens": 50}

        # Mock usage object as dict style
        completion.usage = {"total_tokens": 60}
        usage_sink = {}
        client._call_api([{"role": "user"}], usage_sink=usage_sink)
        assert usage_sink == {"total_tokens": 60}


def test_worker_client_call_api_empty_response():
    with patch("app.llm_engine.client.OpenAI") as mock_openai:
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
            usage=None,
        )
        mock_openai.return_value.chat.completions.create.return_value = completion

        client = WorkerClient(api_key="key")
        with pytest.raises(ValueError, match="Empty response"):
            client._call_api([{"role": "user"}])


def test_worker_client_tagged_block():
    client = WorkerClient(api_key="key")
    res = client._tagged_block("tag", "hello ]]> world")
    assert "<tag>" in res
    assert "<![CDATA[\nhello ]]]" in res


def test_worker_client_context_message():
    client = WorkerClient(api_key="key")
    # Empty context
    res = client._context_message(mode="conservative", context=None)
    assert "<runtime_context>" in res
    assert "retrieval_status" in res

    # Compact repo context
    context = {
        "repo_context": {
            "mode": "compact",
            "repo_full_name": "owner/repo",
            "normalized_repo_url": "https://github.com/owner/repo",
            "default_branch": "main",
            "detected_stack": ["Python"],
            "files_used": ["main.py"],
            "highlights": ["some highlight"],
            "summary_compact": "compact summary text",
        }
    }
    res2 = client._context_message(mode="conservative", context=context)
    assert "Repo Context (ground truth)" in res2
    assert "compact summary text" in res2
    assert "main.py" in res2


def test_worker_client_prompts_example_code_disabled():
    client = WorkerClient(api_key="key")

    # 1. Single agent
    client.agent_generator_prompt = (
        "\n## Example Code (Pseudo-code Skeleton)\ndummy_skeleton_logic\n## TONE & STYLE\n"
    )
    res1 = client._single_agent_prompt(include_example_code=False)
    assert "## Example Code (Pseudo-code Skeleton)" not in res1
    assert "dummy_skeleton_logic" not in res1
    assert "Example code is disabled" in res1

    # 2. Multi agent
    client.multi_agent_planner_prompt = (
        "\n## OPTIONAL SWARM EXAMPLE CODE SECTION\ndummy_skeleton_logic"
    )
    res2 = client._multi_agent_prompt(include_example_code=False)
    assert "## OPTIONAL SWARM EXAMPLE CODE SECTION" not in res2
    assert "dummy_skeleton_logic" not in res2
    assert "Example code is disabled" in res2

    # 3. Skill
    client.skills_generator_prompt = (
        "\n## Examples\n[At least one and at most three concrete invocations]\n- Input:\n- Input:\n"
    )
    res3 = client._skill_prompt(include_example_code=False)
    assert "[At least one and at most three concrete invocations]" not in res3
    assert "Example code is disabled" in res3


def test_worker_client_process_exceptions():
    client = WorkerClient(api_key="key")

    # Missing key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.process("hello")
    client.api_key = "key"

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="did not respond"):
            client.process("hello")

    # APIError
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    # Raise APIError constructed properly for newer openai SDKs
    with patch.object(
        client,
        "_call_api_with_timeout",
        side_effect=APIError("API error", request=MagicMock(), body=None),
    ):
        with pytest.raises(RuntimeError, match="LLM API failed"):
            client.process("hello")

    # Generic Exception
    with patch.object(client, "_call_api_with_timeout", side_effect=Exception("unhandled")):
        with pytest.raises(RuntimeError, match="LLM error"):
            client.process("hello")


def test_worker_client_process_success_and_guardrails():
    client = WorkerClient(api_key="key")
    client.system_prompt = "system"
    client.system_prompt_conservative = "conservative"

    # Successful conservative process, with missing optimized_content (constructed)
    json_response = {
        "ir": {
            "policy": {"risk_level": "low", "execution_mode": "offline"},
            "intents": [],
            "diagnostics": [],
        },
        "system_prompt": "sys prompt",
        "user_prompt": "usr prompt",
        "plan": "plan text",
        "optimized_content": "",
    }
    with patch.object(client, "_call_api_with_timeout", return_value=json.dumps(json_response)):
        res = client.process("hello", mode="conservative")
        assert res.system_prompt == "sys prompt"
        assert res.optimized_content == "usr prompt\n\n---\n\nplan text"

    # Non-conservative mode (default)
    json_response_default = {
        "ir": {
            "policy": {"risk_level": "low", "execution_mode": "offline"},
            "intents": [],
            "diagnostics": [],
        },
        "system_prompt": "sys prompt",
        "user_prompt": "usr prompt",
        "plan": "plan text",
        "optimized_content": "",
    }
    with patch.object(
        client, "_call_api_with_timeout", return_value=json.dumps(json_response_default)
    ):
        res = client.process("hello", mode="default")
        assert res.optimized_content == "sys prompt\n\n---\n\nusr prompt\n\n---\n\nplan text"

    # Guardrails trigger (not safe prompt)
    json_response_unsafe = {
        "ir": {
            "policy": {"risk_level": "low", "execution_mode": "offline"},
            "intents": [],
            "diagnostics": [],
        },
        "system_prompt": "sys prompt with api_key=my-secret-key-123",
        "user_prompt": "usr prompt",
        "plan": "plan",
        "optimized_content": "optimized content with api_key=my-secret-key-123",
    }
    with patch.object(
        client, "_call_api_with_timeout", return_value=json.dumps(json_response_unsafe)
    ):
        res = client.process("hello")
        assert "my-secret-key-123" not in res.system_prompt
        assert "my-secret-key-123" not in res.optimized_content


def test_worker_client_analyze_prompt():
    client = WorkerClient(api_key="key")
    client.coach_prompt = "coach"

    # Normal flow
    report = {
        "score": 90,
        "category_scores": {"clarity": 90},
        "strengths": ["clear"],
        "weaknesses": ["none"],
        "suggestions": ["keep it up"],
        "summary": "excellent",
    }
    with patch.object(client, "_call_api_with_timeout", return_value=json.dumps(report)):
        res = client.analyze_prompt("hello")
        assert res.score == 90
        assert res.summary == "excellent"

    # Missing API Key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.analyze_prompt("hello")
    client.api_key = "key"

    # Missing coach prompt
    client.coach_prompt = ""
    with pytest.raises(RuntimeError, match="Quality Coach prompt not found"):
        client.analyze_prompt("hello")
    client.coach_prompt = "coach"

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.analyze_prompt("hello")

    # Generic error
    with patch.object(client, "_call_api_with_timeout", side_effect=Exception("error")):
        with pytest.raises(RuntimeError, match="error"):
            client.analyze_prompt("hello")


def test_worker_client_optimize_prompt():
    client = WorkerClient(api_key="key")
    client.optimizer_prompt = "optimizer"

    # 1. Success with usage tracking
    with patch.object(
        client, "_call_api_with_timeout", return_value="optimized result"
    ) as mock_call:
        res, usage = client.optimize_prompt("prompt to optimize", max_tokens=100, max_chars=500)
        assert res == "optimized result"
        mock_call.assert_called_once()
        args, _ = mock_call.call_args
        assert "TARGET: Strict maximum of 100 tokens." in args[0][0]["content"]

    # 2. Missing key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.optimize_prompt("hello")
    client.api_key = "key"

    # 3. Fallback when optimizer prompt is missing
    client.optimizer_prompt = ""
    with patch.object(
        client, "_call_api_with_timeout", return_value="fallback optimized"
    ) as mock_call:
        res, _ = client.optimize_prompt("hello")
        assert res == "fallback optimized"
        assert "specialized Prompt Optimizer" in client.optimizer_prompt

    # 4. Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.optimize_prompt("hello")


def test_worker_client_fix_prompt():
    client = WorkerClient(api_key="key")
    client.editor_prompt = "editor"

    fix_res = {
        "fixed_text": "fixed prompt",
        "explanation": "added clarity",
        "changes": ["minor edits"],
    }
    with patch.object(client, "_call_api_with_timeout", return_value=json.dumps(fix_res)):
        res = client.fix_prompt("hello")
        assert res.fixed_text == "fixed prompt"

    # Missing Key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.fix_prompt("hello")
    client.api_key = "key"

    # Fallback editor prompt
    client.editor_prompt = ""
    with patch.object(client, "_call_api_with_timeout", return_value=json.dumps(fix_res)):
        res = client.fix_prompt("hello")
        assert res.fixed_text == "fixed prompt"
        assert "expert editor" in client.editor_prompt

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.fix_prompt("hello")


def test_worker_client_optimize_prompt_english_variant():
    client = WorkerClient(api_key="key")
    client.optimizer_prompt = "optimizer"

    # Success
    with patch.object(
        client, "_call_api_with_timeout", return_value="english variant"
    ) as mock_call:
        res, _ = client.optimize_prompt_english_variant("prompt", max_tokens=150)
        assert res == "english variant"
        args, _ = mock_call.call_args
        assert "compact English variant" in args[0][0]["content"]

    # Missing Key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.optimize_prompt_english_variant("hello")
    client.api_key = "key"

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.optimize_prompt_english_variant("hello")


def test_worker_client_expand_query_intent():
    client = WorkerClient(api_key="key")

    # Success
    with patch.object(client, "_call_api_with_timeout", return_value='{"queries": ["q1", "q2"]}'):
        res = client.expand_query_intent("query")
        assert res == {"queries": ["q1", "q2"]}

    # Missing Key
    client.api_key = "missing_key"
    res_nokey = client.expand_query_intent("query")
    assert res_nokey == {"queries": ["query"]}
    client.api_key = "key"

    # Exception
    with patch.object(client, "_call_api_with_timeout", side_effect=Exception("error")):
        res_err = client.expand_query_intent("query")
        assert res_err == {"queries": ["query"]}


def test_worker_client_generate_agent():
    client = WorkerClient(api_key="key")

    # Single agent
    with patch.object(client, "_call_api_with_timeout", return_value="Markdown content"):
        res = client.generate_agent("task", multi_agent=False)
        assert res == "Markdown content"

    # Multi-agent warning > 4 agents
    multi_response = "# Agent 1\n# Agent 2\n# Agent 3\n# Agent 4\n# Agent 5"
    with patch.object(client, "_call_api_with_timeout", return_value=multi_response):
        with patch("logging.warning") as mock_warn:
            client.generate_agent("task", multi_agent=True)
            mock_warn.assert_called_once()
            assert "exceeded limit" in mock_warn.call_args[0][0]

    # Multi-agent warning 0 agents
    multi_response_none = "No agent headers"
    with patch.object(client, "_call_api_with_timeout", return_value=multi_response_none):
        with patch("logging.warning") as mock_warn:
            client.generate_agent("task", multi_agent=True)
            mock_warn.assert_called_once()
            assert "contains no" in mock_warn.call_args[0][0]

    # Missing key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.generate_agent("hello")
    client.api_key = "key"

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.generate_agent("hello")


def test_worker_client_generate_skill():
    client = WorkerClient(api_key="key")

    # Skill code enabled
    with patch.object(client, "_call_api_with_timeout", return_value="Skill content"):
        res = client.generate_skill("task", include_example_code=True)
        assert res == "Skill content"

    # Skill code disabled (with sanitization)
    plain_content = "## Name\n```\nmy_skill\n```\n## Purpose\nThis is a purpose.\n## Examples\nInput: {} → Output: {}\n"
    with patch.object(client, "_call_api_with_timeout", return_value=plain_content):
        res = client.generate_skill("task", include_example_code=False)
        assert "Examples" not in res
        assert "my_skill" in res

    # Missing key
    client.api_key = "missing_key"
    with pytest.raises(RuntimeError, match="API Key is missing"):
        client.generate_skill("hello")
    client.api_key = "key"

    # Timeout
    with patch.object(client, "_call_api_with_timeout", side_effect=FuturesTimeoutError()):
        with pytest.raises(RuntimeError, match="timed out"):
            client.generate_skill("hello")


def test_sanitize_skill_definition_plain_edge_cases():
    assert _sanitize_skill_definition_plain("") == ""

    text = (
        "## Name\n```my_skill```\n## Purpose\nThis is a purpose.\n## Examples\nThis is examples.\n"
    )
    sanitized = _sanitize_skill_definition_plain(text)
    assert "Purpose" in sanitized
    assert "Examples" not in sanitized
