"""
Tests for Conservative Mode (anti-hallucination) behavior.

Covers:
- Trivial/greeting inputs produce minimal, grounded output (no boilerplate expansion)
- Substantive inputs still produce full expanded prompts
- Conservative mode does not inject invented domains, technologies, or tasks
- Meta-leak detection helper in api/main.py
- emit_expanded_prompt_v2 trivial-input early-exit
"""

from app.compiler import compile_text
from app.compiler import compile_text_v2
from app.emitters import (
    emit_expanded_prompt,
    emit_expanded_prompt_v2,
    _is_trivial_input,
    _minimal_greeting_prompt,
)
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from api.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _force_conservative(monkeypatch):
    """Ensure PROMPT_COMPILER_MODE is conservative for the test."""
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "conservative")


# ---------------------------------------------------------------------------
# _is_trivial_input unit tests
# ---------------------------------------------------------------------------


def test_trivial_input_greeting_english():
    assert _is_trivial_input("hello", "general", "low") is True


def test_trivial_input_greeting_turkish():
    assert _is_trivial_input("merhaba", "general", "low") is True


def test_trivial_input_short_general():
    assert _is_trivial_input("hi there", "general", "low") is True


def test_trivial_input_not_triggered_for_coding():
    # Even a short input with a non-general domain should NOT be trivial
    assert _is_trivial_input("sort list", "coding", "low") is False


def test_trivial_input_not_triggered_for_long_text():
    long_text = "Please write a Python function that reads a CSV file and returns a sorted list"
    assert _is_trivial_input(long_text, "general", "low") is False


def test_trivial_input_not_triggered_for_medium_complexity():
    assert _is_trivial_input("hello", "general", "medium") is False


# ---------------------------------------------------------------------------
# _minimal_greeting_prompt unit tests
# ---------------------------------------------------------------------------


def test_minimal_greeting_english():
    result = _minimal_greeting_prompt("hello", "en")
    assert "user message" in result.lower()
    assert '"hello"' in result.lower()
    assert "how can i help" not in result.lower()


def test_minimal_greeting_turkish():
    result = _minimal_greeting_prompt("merhaba", "tr")
    assert "kullanici mesaji" in result.lower()
    assert '"merhaba"' in result.lower()
    assert "yardimci olabilirim" not in result.lower()


def test_minimal_greeting_no_boilerplate():
    result = _minimal_greeting_prompt("hello", "en")
    # Must NOT contain the generic expanded-prompt boilerplate
    assert "Generate clear, actionable suggestions" not in result
    assert "Follow-up Questions" not in result
    assert "Which success metrics" not in result
    assert "Example output format" not in result


def test_minimal_greeting_is_instruction_not_assistant_reply():
    result = _minimal_greeting_prompt("hello", "en")
    assert "reply briefly" in result.lower()
    assert "hello!" not in result.lower()
    assert "how can i help" not in result.lower()


# ---------------------------------------------------------------------------
# emit_expanded_prompt: trivial input early-exit (conservative=True)
# ---------------------------------------------------------------------------


def test_greeting_conservative_returns_minimal(monkeypatch):
    _force_conservative(monkeypatch)
    ir = compile_text("merhaba")
    result = emit_expanded_prompt(ir, conservative=True)
    assert "Generate clear, actionable suggestions" not in result
    assert "Follow-up Questions" not in result
    assert "Which success metrics" not in result
    # Must still return something non-empty
    assert len(result.strip()) > 0


def test_greeting_conservative_no_hallucination(monkeypatch):
    _force_conservative(monkeypatch)
    ir = compile_text("hello")
    result = emit_expanded_prompt(ir, conservative=True)
    # No invented domains, technologies, or task scaffolding
    assert "python" not in result.lower()
    assert "code" not in result.lower()
    assert "developer" not in result.lower()
    assert "write a" not in result.lower()


def test_substantive_input_still_expands_conservative(monkeypatch):
    _force_conservative(monkeypatch)
    ir = compile_text("Write a Python script that reads a JSON file and prints each key")
    result = emit_expanded_prompt(ir, conservative=True)
    # Substantive inputs should still get the full expanded template
    assert "Expanded Prompt" in result or "Genişletilmiş İstem" in result


def test_conservative_note_present_for_substantive(monkeypatch):
    _force_conservative(monkeypatch)
    ir = compile_text("Analyze stock market trends for a beginner investor")
    result = emit_expanded_prompt(ir, conservative=True)
    # Should include the anti-hallucination note, not the fabrication note
    assert "fabricate" not in result.lower() or "do not fabricate" in result.lower()
    assert "missing details will be filled" not in result.lower()


# ---------------------------------------------------------------------------
# emit_expanded_prompt_v2: trivial input early-exit (conservative env)
# ---------------------------------------------------------------------------


def test_greeting_v2_conservative_returns_minimal(monkeypatch):
    _force_conservative(monkeypatch)
    ir2 = compile_text_v2("hello", offline_only=True)
    result = emit_expanded_prompt_v2(ir2)
    assert "Generate clear, actionable suggestions" not in result
    assert "Which success metrics" not in result
    assert len(result.strip()) > 0


def test_greeting_v2_turkish_conservative_returns_minimal(monkeypatch):
    _force_conservative(monkeypatch)
    ir2 = compile_text_v2("merhaba", offline_only=True)
    result = emit_expanded_prompt_v2(ir2)
    assert "Generate clear, actionable suggestions" not in result
    assert len(result.strip()) > 0


def test_greeting_v2_is_instruction_not_chat_reply(monkeypatch):
    _force_conservative(monkeypatch)
    ir2 = compile_text_v2("merhaba", offline_only=True)
    result = emit_expanded_prompt_v2(ir2)
    assert "kullanici mesaji" in result.lower()
    assert "yardimci olabilirim" not in result.lower()


def test_compile_endpoint_forces_instruction_prompt_for_trivial_input(monkeypatch):
    _force_conservative(monkeypatch)
    ir2 = compile_text_v2("merhaba", offline_only=True)
    mock_response = MagicMock()
    mock_response.ir = ir2
    mock_response.system_prompt = ""
    mock_response.user_prompt = "Merhaba! Nasil yardimci olabilirim?"
    mock_response.plan = "1. Selam ver"
    mock_response.optimized_content = "Merhaba! Nasil yardimci olabilirim?"

    mock_compiler = MagicMock()
    mock_compiler.compile.return_value = mock_response

    with patch("api.main.get_compiler", return_value=mock_compiler):
        client = TestClient(app)
        response = client.post(
            "/compile",
            json={"text": "merhaba", "v2": True, "render_v2_prompts": True, "mode": "conservative"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "kullanici mesaji" in data["expanded_prompt_v2"].lower()
    assert "yardimci olabilirim" not in data["expanded_prompt_v2"].lower()


def test_substantive_v2_still_expands(monkeypatch):
    _force_conservative(monkeypatch)
    ir2 = compile_text_v2(
        "Write a REST API endpoint in FastAPI that accepts a JSON body and returns a summary",
        offline_only=True,
    )
    result = emit_expanded_prompt_v2(ir2)
    assert "Expanded Prompt" in result or "Genişletilmiş İstem" in result


# ---------------------------------------------------------------------------
# Meta-leak detection helper (api/main.py)
# ---------------------------------------------------------------------------


def test_meta_leak_detection_import():
    """Ensure _is_meta_leaked is importable and works correctly."""
    from api.main import _is_meta_leaked  # type: ignore

    # Should detect leaked internal instructions
    assert _is_meta_leaked("Output only valid JSON") is True
    assert _is_meta_leaked("Sadece gecerli JSON ciktisi.") is True
    assert _is_meta_leaked("Only valid JSON") is True
    assert _is_meta_leaked("Return only JSON") is True


def test_meta_leak_not_triggered_for_normal_prompts():
    from api.main import _is_meta_leaked  # type: ignore

    assert _is_meta_leaked("You are a friendly Python developer assistant.") is False
    assert _is_meta_leaked("Sen yardimci bir asistansin. Kullaniciya merhaba de.") is False
    assert _is_meta_leaked("Write clean, readable Python code with docstrings.") is False


def test_meta_leak_not_triggered_for_long_text():
    from api.main import _is_meta_leaked  # type: ignore

    # A long text that incidentally contains "json" should NOT be flagged
    long = (
        "You are a data engineer. Your job is to transform input records into "
        "valid JSON output, validate each field, and return a structured response. "
        "Do not include extra commentary in your output."
    )
    assert _is_meta_leaked(long) is False


# ---------------------------------------------------------------------------
# Conservative mode: non-default (aggressive) mode preserves fabrication note
# ---------------------------------------------------------------------------


def test_aggressive_mode_fabrication_note(monkeypatch):
    monkeypatch.setenv("PROMPT_COMPILER_MODE", "default")
    ir = compile_text("Analyze stock market trends for a beginner investor")
    result = emit_expanded_prompt(ir, conservative=False)
    assert "Missing details will be filled" in result or "reasonable sample values" in result
