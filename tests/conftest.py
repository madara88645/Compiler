import os
import tempfile
from pathlib import Path

import pytest

_TEST_RUNTIME_ROOT = Path(__file__).resolve().parent.parent / ".tmp-test-run"
_TEST_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
_TEST_SESSION_DIR = Path(tempfile.mkdtemp(prefix="pytest-", dir=str(_TEST_RUNTIME_ROOT))).resolve()
_TEST_DB_DIR = (_TEST_SESSION_DIR / "db").resolve()
_TEST_DB_DIR.mkdir(parents=True, exist_ok=True)

for env_name in ("TMP", "TEMP", "TMPDIR"):
    os.environ[env_name] = str(_TEST_SESSION_DIR)
tempfile.tempdir = str(_TEST_SESSION_DIR)
os.environ["DB_DIR"] = str(_TEST_DB_DIR)

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
    import os

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
