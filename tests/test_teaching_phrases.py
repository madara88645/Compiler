"""Teaching phrase detection and level/duration heuristics."""

import pytest

from app.compiler import compile_text, compile_text_v2
from app.heuristics import detect_teaching_intent


@pytest.mark.parametrize(
    "prompt",
    [
        "teach me binary search with examples",
        "explain recursion step by step",
        "tutorial on docker basics",
        "guide me through python lists",
        "bana grafik veri yapısını öğret, örneklerle anlat",
        "sıfırdan sql dersi anlat",
        "machine learning öğrenmek istiyorum",
    ],
)
def test_detect_teaching_intent_true_for_teaching_phrases(prompt: str):
    assert detect_teaching_intent(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "My React app re-renders too much",
        "List three ideas for a birthday gift",
        "Implement secure login sessions",
        "write a blog post about travel",
        "",
    ],
)
def test_detect_teaching_intent_false_for_non_teaching_phrases(prompt: str):
    assert detect_teaching_intent(prompt) is False


@pytest.mark.parametrize(
    "prompt,expected_level",
    [
        ("teach me biology beginner level", "beginner"),
        ("tutorial on history intermediate level", "intermediate"),
        ("explain philosophy advanced level", "advanced"),
        ("başlangıç seviyesinde coğrafya öğret", "beginner"),
        ("orta seviye edebiyat dersi", "intermediate"),
        ("ileri seviye felsefe anlat", "advanced"),
    ],
)
def test_teaching_level_heuristic_sets_inputs_and_constraints(prompt, expected_level):
    ir = compile_text(prompt)
    assert ir.persona == "teacher"
    assert ir.inputs.get("level") == expected_level
    assert any(
        origin.startswith("teaching_level")
        for origin in (ir.metadata.get("constraint_origins") or {}).values()
    )


@pytest.mark.parametrize(
    "prompt,expected_duration",
    [
        ("teach me photosynthesis in 10 minutes beginner level", "10m"),
        ("half hour tutorial about ancient history", "30m"),
        ("yarım saat içinde bana temel coğrafya öğret", "30m"),
        ("15 dakikada coğrafya öğret", "15m"),
        ("explain supply and demand in 1 hour", "1h"),
    ],
)
def test_teaching_duration_heuristic_sets_inputs_and_constraints(prompt, expected_duration):
    ir = compile_text(prompt)
    assert ir.persona == "teacher"
    assert ir.inputs.get("duration") == expected_duration
    assert any(
        origin.startswith("teaching_duration")
        for origin in (ir.metadata.get("constraint_origins") or {}).values()
    )


def test_compile_v2_teaching_phrase_carries_level_and_duration_constraints():
    ir_v2 = compile_text_v2("teach me photosynthesis in 10 minutes beginner level")
    assert "teaching" in ir_v2.intents
    assert ir_v2.inputs.get("level") == "beginner"
    assert ir_v2.inputs.get("duration") == "10m"
    origins = {c.origin for c in ir_v2.constraints}
    assert any(o.startswith("teaching_level") for o in origins)
    assert any(o.startswith("teaching_duration") for o in origins)
