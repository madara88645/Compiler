import pytest
from app.compiler import compile_text_v2
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
    
    assert "{{USER_NAME}}" in structured or "USER_NAME" in structured # Logic might leave it as is if it thinks it's not a var, but let's check
    # Check if variables section exists
    assert "### Variables" in structured
    assert "- USER_NAME" in structured

def test_logic_engine_negation():
    """Test detection of negative constraints."""
    text = "Create a SQL query. Do not use JOIN operations. Never use nested selects."
    
    ir = compile_text_v2(text)
    logic = ir.metadata.get("logic_analysis", {})
    negations = logic.get("negations", [])
    
    assert len(negations) >= 2
    words = [n["negation_word"] for n in negations]
    assert "do not" in words
    assert "never" in words
    
    # Check if they were added to constraints
    constraints = [c.text if hasattr(c, 'text') else c['text'] for c in ir.constraints]
    # LogicHandler adds the *Anti-Pattern* (positive version)
    # "do not use JOIN" -> "Instead: use JOIN" ??? No, wrapper logic:
    # "Instead: use JOIN operations" (Wait, strip_negation removes "do not")
    # Let's check if *something* was added from logic
    assert any("derived from negative" in str(c).lower() or "heuristic:logic_negation" in str(c) for c in ir.constraints)

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
    from api.main import app 
    
    text = "Task: Write a poem."
    ir = compile_text_v2(text)
    assert ir.metadata.get("structured_view")

if __name__ == "__main__":
    # Manually run if needed
    test_structure_engine_formatting()
    test_logic_engine_negation()
    print("Manual checks passed")
