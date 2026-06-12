import os
import tempfile
from pathlib import Path

import pytest
from tests.runtime_bootstrap import apply_test_runtime, prepare_test_runtime

_TEST_RUNTIME_ROOT = Path(__file__).resolve().parent.parent / ".tmp-test-run"
_FALLBACK_RUNTIME_ROOTS = [Path(tempfile.gettempdir()) / "promptc-pytest-runtime"]
_TEST_RUNTIME = prepare_test_runtime(
    preferred_root=_TEST_RUNTIME_ROOT,
    fallback_roots=_FALLBACK_RUNTIME_ROOTS,
)
_TEST_SESSION_DIR = _TEST_RUNTIME.session_dir
_TEST_DB_DIR = _TEST_RUNTIME.db_dir

apply_test_runtime(_TEST_RUNTIME)

from api.main import app  # noqa: E402
from api.auth import verify_api_key, APIKey  # noqa: E402


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run tests marked live that call real upstream services.",
    )


def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--run-live") or os.environ.get("PROMPTC_RUN_LIVE_TESTS") == "1"
    if run_live:
        return

    skip_live = pytest.mark.skip(reason="need --run-live or PROMPTC_RUN_LIVE_TESTS=1 to run")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def override_auth_dependencies(request):
    if request.module.__name__ == "tests.test_auth_fast_path" or request.node.get_closest_marker(
        "auth_required"
    ):
        yield
        return

    app.dependency_overrides[verify_api_key] = lambda: APIKey(
        key="test", owner="test", is_active=True
    )
    yield
    app.dependency_overrides.pop(verify_api_key, None)


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # Also clear rate limits so tests don't fail rate limiting
    from api.auth import RATE_LIMIT_STORE

    RATE_LIMIT_STORE.clear()


@pytest.fixture(autouse=True)
def _reset_security_env(monkeypatch):
    monkeypatch.delenv("PROMPTC_REQUIRE_API_KEY_FOR_ALL", raising=False)
