from app.models_v2 import ConstraintV2, IRv2
from app.validator import PromptValidator


def make_ir(**overrides) -> IRv2:
    base = {
        "persona": "developer",
        "role": "Senior backend engineer and code reviewer",
        "domain": "software",
        "goals": ["Build a reliable API endpoint"],
        "tasks": ["Implement validation with tests"],
        "constraints": [ConstraintV2(id="scope", text="stay within the repository")],
        "tone": ["professional"],
        "output_format": "markdown",
        "metadata": {},
    }
    base.update(overrides)
    return IRv2(**base)


def issue_messages(ir: IRv2) -> list[str]:
    return [issue.message for issue in PromptValidator().validate(ir).issues]


def test_validator_flags_overly_broad_goals():
    ir = make_ir(goals=["cover everything about the system in one answer"])

    assert any("Goal may be too broad" in message for message in issue_messages(ir))


def test_validator_flags_complex_tasks_without_examples():
    ir = make_ir(
        tasks=["design a distributed migration plan with rollback steps"],
        metadata={"complexity_score": 0.9},
        examples=[],
    )

    assert "Complex task without examples" in issue_messages(ir)


def test_validator_flags_teaching_intent_without_level_constraint():
    ir = make_ir(
        intents=["teaching"],
        constraints=[ConstraintV2(id="scope", text="use practical examples")],
    )

    assert "Teaching intent without skill level" in issue_messages(ir)


def test_validator_flags_conflicting_constraint_pairs():
    ir = make_ir(
        goals=["keep the answer brief and concise"],
        constraints=[
            ConstraintV2(
                id="detail",
                text="provide a detailed and comprehensive explanation",
            )
        ],
    )

    assert any("Potentially conflicting constraints" in message for message in issue_messages(ir))


def test_validator_flags_formal_tone_with_casual_persona():
    ir = make_ir(persona="casual coding buddy", tone=["formal"])

    assert "Tone and persona mismatch" in issue_messages(ir)
