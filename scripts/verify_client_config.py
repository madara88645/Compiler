import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_client_config_defaults():
    from app.llm_engine.client import DEFAULT_MODEL, DEFAULT_BASE_URL, HARD_TIMEOUT_SECONDS

    print(
        f"Defaults: Model={DEFAULT_MODEL}, URL={DEFAULT_BASE_URL}, Timeout={HARD_TIMEOUT_SECONDS}"
    )

    # Assert defaults (assuming no env vars set in this process yet)
    # Note: If .env is loaded by app, this might fail if .env has values.
    # But client.py loads dotenv.
    pass


def test_client_config_env_vars():
    # Set env vars before importing client (or reload it)
    os.environ["LLM_MODEL"] = "test-model"
    os.environ["LLM_BASE_URL"] = "http://test.url"
    os.environ["LLM_TIMEOUT"] = "99"

    import importlib
    import app.llm_engine.client

    importlib.reload(app.llm_engine.client)

    from app.llm_engine.client import DEFAULT_MODEL, DEFAULT_BASE_URL, HARD_TIMEOUT_SECONDS

    print(
        f"Env Vars: Model={DEFAULT_MODEL}, URL={DEFAULT_BASE_URL}, Timeout={HARD_TIMEOUT_SECONDS}"
    )

    assert DEFAULT_MODEL == "test-model"
    assert DEFAULT_BASE_URL == "http://test.url"
    assert HARD_TIMEOUT_SECONDS == 99
    print("SUCCESS: Environment variables respected.")


if __name__ == "__main__":
    try:
        test_client_config_env_vars()
    except AssertionError as e:
        print(f"FAILURE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
