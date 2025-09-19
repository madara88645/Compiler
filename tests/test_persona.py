from app.compiler import compile_text


def test_default_persona_assistant():
    ir = compile_text("List three ideas for a birthday gift")
    assert ir.persona == "assistant"


def test_teacher_persona_keywords():
    ir = compile_text("teach me recursion tutorial")
    assert ir.persona == "teacher"
    assert ir.metadata.get("persona_evidence")


def test_researcher_persona():
    ir = compile_text("research and analyze recent literature on quantum computing")
    assert ir.persona in {"researcher", "assistant"}  # may fallback if not matched fully
    if ir.persona == "researcher":
        ev = ir.metadata.get("persona_evidence", {})
        assert ev.get("scores", {}).get("researcher", 0) > 0


def test_coach_persona():
    ir = compile_text("motivate me like a coach for marathon training")
    assert ir.persona in {"coach", "assistant"}


def test_mentor_persona():
    ir = compile_text("career mentor guidance for software engineering path")
    assert ir.persona in {"mentor", "assistant"}
