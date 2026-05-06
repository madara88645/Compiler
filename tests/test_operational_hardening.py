import io
import logging
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from api.shared import logger as api_logger


def test_health_does_not_initialize_compiler_on_startup(monkeypatch):
    monkeypatch.setattr("api.main.hybrid_compiler", None)

    def fail_if_called():
        raise AssertionError("get_compiler should not run during app startup")

    monkeypatch.setattr("api.main.get_compiler", fail_if_called)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_request_emits_completion_log(monkeypatch):
    stream = io.StringIO()
    for handler in api_logger.handlers:
        monkeypatch.setattr(handler, "stream", stream)

    with TestClient(app) as client:
        response = client.get("/health", headers={"user-agent": "pytest-agent"})

    assert response.status_code == 200
    output = stream.getvalue()
    assert "request completed" in output
    assert "method=GET" in output
    assert "path=/health" in output
    assert "status_code=200" in output


def test_api_logger_is_info_enabled_by_default():
    assert api_logger.isEnabledFor(logging.INFO)


def test_api_logger_has_a_handler():
    assert api_logger.handlers


def test_fly_config_does_not_allow_wildcard_cors():
    fly_toml = Path(__file__).resolve().parents[1] / "fly.toml"
    contents = fly_toml.read_text(encoding="utf-8")

    assert 'ALLOWED_ORIGINS = "*"' not in contents
