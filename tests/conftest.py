import pytest
from api.main import app
from api.auth import verify_api_key, APIKey

@pytest.fixture(autouse=True)
def override_auth_dependencies(request):
    if request.module.__name__ == "tests.test_auth_fast_path":
        yield
        return

    app.dependency_overrides[verify_api_key] = lambda: APIKey(key="test", owner="test", is_active=True)
    yield
    app.dependency_overrides.pop(verify_api_key, None)

@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # Also clear rate limits so tests don't fail rate limiting
    from api.auth import RATE_LIMIT_STORE
    RATE_LIMIT_STORE.clear()
