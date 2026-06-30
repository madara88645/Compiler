"""Persona/role must fit the request: right language, no teaching false-positive.

Regressions found by the value benchmark:
- "Write a Python function..." produced role "Expert JavaScript Developer"
  (the implied-persona tiebreaker let "function " beat the language).
- "My React app re-renders too much..." produced persona "teacher" because the
  teaching matcher found "ders" inside "re-nders" (substring match).
- "Build me a dashboard..." stayed persona "assistant" with no developer context.
"""

from app.compiler import compile_text_v2
from app.heuristics import detect_teaching_intent


def test_python_request_gets_python_role_not_javascript():
    ir = compile_text_v2(
        "Write a Python function to parse nginx logs and detect brute-force login attempts"
    )
    assert "python" in ir.role.lower()
    assert "javascript" not in ir.role.lower()


def test_renders_does_not_trigger_teaching_intent():
    assert detect_teaching_intent("My React app re-renders too much") is False


def test_real_teaching_intent_still_detected():
    assert detect_teaching_intent("teach me recursion with a tutorial") is True


def test_react_performance_is_not_teacher():
    ir = compile_text_v2("My React app re-renders too much, help me fix the performance")
    assert ir.persona != "teacher"
    assert ir.persona in {"developer", "expert"}


def test_dashboard_request_gets_developer_persona():
    ir = compile_text_v2("Build me a dashboard that shows my Stripe revenue")
    assert ir.persona in {"developer", "expert"}
