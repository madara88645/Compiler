import os
from unittest.mock import patch
import pytest

@pytest.fixture(autouse=True)
def wipe_env(monkeypatch):
    # Make sure we don't have these set so we trigger the fallback code logic during tests
    monkeypatch.delenv("USERPROFILE", raising=False)

def test_history_manager_secure_path():
    with patch("os.name", "nt"):
        # We need to reload the module to trigger the initialization logic
        import importlib
        import app.history.manager
        importlib.reload(app.history.manager)

        path = app.history.manager.DEFAULT_DB_PATH

        # Verify it uses the user's home directory fallback instead of C:\
        assert "C:\\" not in path or os.path.expanduser("~") == "C:\\"
        assert path.endswith(".promptc_history.db")

def test_rag_simple_index_secure_path():
    with patch("os.name", "nt"):
        import importlib
        import app.rag.simple_index
        importlib.reload(app.rag.simple_index)

        path = app.rag.simple_index.DEFAULT_DB_PATH

        # Verify it uses the user's home directory fallback instead of C:\
        assert "C:\\" not in path or os.path.expanduser("~") == "C:\\"
        assert path.endswith(".promptc_index_v3.db")
