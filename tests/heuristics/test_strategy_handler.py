import pytest
from app.heuristics.handlers.strategy import StrategyHandler


@pytest.fixture
def handler():
    return StrategyHandler()


# --------------------------------------------------------------------------
# CoT INJECTION TESTS
# --------------------------------------------------------------------------


def test_cot_injection_high_complexity(handler):
    """CoT should be injected when complexity > 70."""
    result = handler.process(
        prompt_text="Explain quantum entanglement",
        complexity_score=85,
    )

    assert len(result.system_prompt_additions) >= 1
    cot_block = result.system_prompt_additions[0]
    assert "step" in cot_block.lower() or "approach" in cot_block.lower()
    assert "CoT injected" in str(result.strategy_notes)


def test_cot_not_injected_low_complexity(handler):
    """CoT should NOT be injected when complexity <= 70."""
    result = handler.process(
        prompt_text="What is 2 + 2?",
        complexity_score=30,
    )

    # Should not have CoT note
    assert not any("CoT" in note for note in result.strategy_notes)


def test_cot_skipped_if_already_present(handler):
    """CoT should not duplicate if already in prompt."""
    result = handler.process(
        prompt_text="Think step by step about this problem",
        complexity_score=90,
    )

    # Should skip CoT injection
    cot_notes = [n for n in result.strategy_notes if "CoT" in n]
    assert len(cot_notes) == 0


# --------------------------------------------------------------------------
# FEW-SHOT TESTS
# --------------------------------------------------------------------------


def test_few_shot_classification_task(handler):
    """Few-shot should be suggested for classification tasks."""
    result = handler.process(
        prompt_text="Classify these emails as spam or not spam",
        complexity_score=50,
    )

    assert result.few_shot_suggestion is not None
    assert "Example" in result.few_shot_suggestion
    assert "Label" in result.few_shot_suggestion


def test_few_shot_transformation_task(handler):
    """Few-shot should be suggested for transformation tasks."""
    result = handler.process(
        prompt_text="Convert these sentences to passive voice",
        complexity_score=50,
    )

    assert result.few_shot_suggestion is not None
    assert "Example" in result.few_shot_suggestion
    assert "Output" in result.few_shot_suggestion


def test_few_shot_with_json_format(handler):
    """Few-shot should mention JSON format if specified."""
    result = handler.process(
        prompt_text="Classify the data",
        task_type="classification",
        output_format="JSON",
    )

    assert "JSON" in result.few_shot_suggestion


# --------------------------------------------------------------------------
# PERSONA DEEPENER TESTS
# --------------------------------------------------------------------------


def test_persona_teacher(handler):
    """Teacher persona should add educational traits."""
    result = handler.process(
        prompt_text="Act as a teacher and explain calculus",
        complexity_score=50,
    )

    assert len(result.persona_traits) > 0
    assert any("Socratic" in trait or "Patient" in trait for trait in result.persona_traits)


def test_persona_auditor(handler):
    """Auditor persona should add analytical traits."""
    result = handler.process(
        prompt_text="You are an auditor reviewing this code",
        complexity_score=50,
    )

    assert len(result.persona_traits) > 0
    assert any("Skeptical" in trait or "Detail" in trait for trait in result.persona_traits)


def test_explicit_persona_override(handler):
    """Explicit persona parameter should override detection."""
    result = handler.process(
        prompt_text="Help me with this task",  # No persona in text
        persona="mentor",
        complexity_score=50,
    )

    assert len(result.persona_traits) > 0
    assert any("wisdom" in trait.lower() for trait in result.persona_traits)


# --------------------------------------------------------------------------
# INTEGRATION TESTS
# --------------------------------------------------------------------------


def test_apply_to_prompt(handler):
    """Test applying strategy results to a prompt."""
    result = handler.process(
        prompt_text="Act as a teacher and classify these items",
        complexity_score=75,
    )

    base_prompt = "You are a helpful assistant."
    enhanced = handler.apply_to_prompt(base_prompt, result)

    # Should contain original + additions
    assert "helpful assistant" in enhanced
    assert "---" in enhanced  # Separator
    assert len(enhanced) > len(base_prompt)


def test_combined_strategies(handler):
    """Multiple strategies should combine correctly."""
    result = handler.process(
        prompt_text="Act as an expert analyst to classify user feedback",
        complexity_score=80,
        output_format="JSON",
    )

    # Should have CoT + Few-shot + Persona
    assert len(result.strategy_notes) >= 2
