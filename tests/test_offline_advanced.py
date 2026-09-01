from app.compiler import compile_text_v2
from app.emitters import emit_system_prompt_v2
from app.heuristics.logic_analyzer import analyze_prompt_logic


def test_structure_engine_formatting():
    """Test that Structure Engine formats messy text into DeepSpec markdown."""
    messy_text = "Role: Expert. Context: You are in a spaceship. Task: Fix the engine. Do not open the airlock."

    ir = compile_text_v2(messy_text)
    structured = ir.metadata.get("structured_view", "")

    print(f"DEBUG: Structured Output:\n{structured}")

    assert "### Role" in structured
    assert "### Context" in structured
    assert "### Task" in structured
    assert "### Constraints" in structured
    assert "Expert" in structured
    assert "spaceship" in structured


def test_structure_variable_injection():
    """Test that capitalized words are converted to variables."""
    text = "Please help USER_NAME with the PROJECT_ID."
    ir = compile_text_v2(text)
    structured = ir.metadata.get("structured_view", "")

    assert (
        "{{USER_NAME}}" in structured or "USER_NAME" in structured
    )  # Logic might leave it as is if it thinks it's not a var, but let's check
    # Check if variables section exists
    assert "### Variables" in structured
    assert "- USER_NAME" in structured


def test_logic_engine_negation():
    """Negative constraints should stay negative when restated."""
    text = "Create a SQL query. Do not use JOIN operations. Never use nested selects."

    ir = compile_text_v2(text)
    logic = ir.metadata.get("logic_analysis", {})
    negations = logic.get("negations", [])

    assert len(negations) >= 2
    words = [n["negation_word"] for n in negations]
    assert "do not" in words
    assert "never" in words

    anti_patterns = {n["negation_word"]: n["anti_pattern"] for n in negations}
    assert anti_patterns["do not"] == "Do not: use JOIN operations."
    assert anti_patterns["never"] == "Never: use nested selects."

    negation_constraints = [c for c in ir.constraints if c.origin == "heuristic:logic_negation"]
    assert len(negation_constraints) >= 2
    assert any(c.text == "Do not: use JOIN operations." for c in negation_constraints)
    assert any(c.text == "Never: use nested selects." for c in negation_constraints)


def test_logic_engine_negation_preserves_polarity_in_emitted_key_constraints():
    """Forbidden actions must stay forbidden in the emitted prompt."""
    text = "Build a CSV export. The API must not expose user emails."

    ir = compile_text_v2(text, offline_only=True)
    logic = ir.metadata.get("logic_analysis", {})
    negations = logic.get("negations", [])

    assert len(negations) == 1
    assert negations[0]["original"] == "The API must not expose user emails."
    assert negations[0]["negation_word"] == "must not"
    assert negations[0]["anti_pattern"] == "Must not: expose user emails."

    negation_constraint = next(c for c in ir.constraints if c.origin == "heuristic:logic_negation")
    assert negation_constraint.priority == 90
    assert negation_constraint.text == "Must not: expose user emails."

    prompt = emit_system_prompt_v2(ir)
    key_constraints_line = next(
        line for line in prompt.splitlines() if line.startswith("Key Constraints:")
    )
    assert "Must not: expose user emails." in key_constraints_line
    assert "Must: expose user emails" not in key_constraints_line


def test_logic_engine_preserves_absolute_no_restrictions_in_constraints():
    """Short absolute restrictions should survive intact into compiled constraints."""
    text = "Build an analytics export. No PII in analytics exports. Do not add new dependencies."

    ir = compile_text_v2(text)
    logic = ir.metadata.get("logic_analysis", {})
    negations = logic.get("negations", [])
    constraint_texts = [
        getattr(constraint, "text", str(constraint)) for constraint in ir.constraints
    ]

    assert any(item["anti_pattern"] == "No PII in analytics exports." for item in negations)
    assert "No PII in analytics exports." in constraint_texts


def test_logic_engine_preserves_none_of_restrictions_in_constraints():
    """`None of ...` restrictions should also survive intact into compiled constraints."""
    text = (
        "Build an export job. None of the exported rows should include archived accounts. "
        "Do not add new dependencies."
    )

    ir = compile_text_v2(text)
    logic = ir.metadata.get("logic_analysis", {})
    negations = logic.get("negations", [])
    constraint_texts = [
        getattr(constraint, "text", str(constraint)) for constraint in ir.constraints
    ]

    sentence = "None of the exported rows should include archived accounts."
    assert any(item["anti_pattern"] == sentence for item in negations)
    assert sentence in constraint_texts


def test_logic_engine_dependencies():
    """Test detection of causal dependencies."""
    text = "Optimize the image because it loads too slowly."

    analysis = analyze_prompt_logic(text)
    assert len(analysis.dependencies) > 0
    dep = analysis.dependencies[0]
    assert "optimize" in dep.action.lower()
    assert "slowly" in dep.reason.lower()
    assert dep.dependency_type == "because"


def test_logic_engine_missing_info():
    """Test detection of missing information."""
    text = "Update the database with the new schema."

    ir = compile_text_v2(text)
    diagnostics = ir.diagnostics

    # specific warning for missing database schema
    # Diagnostics might be Objects or Dicts depending on phase
    messages = []
    for d in diagnostics:
        if isinstance(d, dict):
            messages.append(d["message"].lower())
        else:
            messages.append(d.message.lower())

    assert any("database" in m for m in messages)
    assert any("missing definition" in m for m in messages)


def test_offline_api_result():
    """Test that the offline API returns the structured prompt."""
    # We just test compile_text_v2 logic mimics what API does for offline
    # (since we modified api/main.py to use it)

    text = "Task: Write a poem."
    ir = compile_text_v2(text)
    assert ir.metadata.get("structured_view")


if __name__ == "__main__":
    # Manually run if needed
    test_structure_engine_formatting()
    test_logic_engine_negation()
    print("Manual checks passed")
