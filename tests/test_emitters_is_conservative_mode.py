"""Unit tests for app.emitters._is_conservative_mode.

Reached indirectly today via emit_expanded_prompt/emit_plan tests that force
PROMPT_COMPILER_MODE through a fixture, but the function itself (explicit
override vs. env var vs. default) had no direct test.
"""

from __future__ import annotations

from app.emitters import _is_conservative_mode


class TestIsConservativeMode:
    def test_explicit_true_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
        assert _is_conservative_mode(True) is True

    def test_explicit_false_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
        assert _is_conservative_mode(False) is False

    def test_env_var_conservative_is_conservative(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")
        assert _is_conservative_mode(None) is True

    def test_env_var_default_is_not_conservative(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
        assert _is_conservative_mode(None) is False

    def test_env_var_is_case_and_whitespace_insensitive(self, monkeypatch):
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "  DEFAULT  ")
        assert _is_conservative_mode(None) is False

    def test_missing_env_var_defaults_to_conservative(self, monkeypatch):
        monkeypatch.delenv("PROMPT_COMPILER_MODE", raising=False)
        assert _is_conservative_mode(None) is True

    def test_unrecognized_env_var_value_is_conservative(self, monkeypatch):
        # Only the literal "default" opts out of conservative mode.
        monkeypatch.setenv("PROMPT_COMPILER_MODE", "aggressive")
        assert _is_conservative_mode(None) is True
