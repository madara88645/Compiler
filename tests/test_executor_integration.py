from app.llm.providers import MockProvider
from app.llm.base import ProviderConfig
from app.testing.runner import LLMExecutor


def test_llm_executor_integration():
    print("Testing LLMExecutor with MockProvider...")

    # 1. Setup
    config = ProviderConfig(model="default-model")
    provider = MockProvider(config)
    executor = LLMExecutor(provider)

    # 2. Test basic execution
    prompt = "Hello world"
    exec_config = {"model": "override-model", "temperature": 0.5}

    print(f"Executing with config: {exec_config}")
    response = executor.execute(prompt, exec_config)

    print(f"Response: {response}")
    assert response == "MOCKED RESPONSE"

    # 3. Test system prompt extraction
    prompt_json = "Generate JSON"
    exec_config_json = {"system_prompt": "You are a JSON machine", "model": "json-model"}

    print("Executing with JSON prompt and system prompt...")
    response_json = executor.execute(prompt_json, exec_config_json)

    print(f"Response JSON: {response_json}")
    assert "variations" in response_json

    print("✅ LLMExecutor integration test passed!")


if __name__ == "__main__":
    test_llm_executor_integration()
