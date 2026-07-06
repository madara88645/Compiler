"""Coverage for three pure app.compiler helpers that had no direct tests:

- decompose_task: splits a task string into ordered sub-steps.
- generate_trace: builds a deterministic debug trace from IR metadata.
- optimize_ir: dedupes goals/tasks by a first-60-chars key and injects a
  domain baseline constraint (EN/TR) when missing.

These are exercised directly (not just through build_steps/compile_text_v2)
so regressions in the underlying logic surface here first.
"""

from app.compiler import decompose_task, generate_trace, optimize_ir
from app.models import IR


# ---------------------------------------------------------------------------
# decompose_task
# ---------------------------------------------------------------------------


def test_decompose_task_and_conjunction_splits_in_two():
    parts = decompose_task("parse the access log and email a daily summary to the team")
    assert parts == ["parse the access log", "email a daily summary to the team"]


def test_decompose_task_then_conjunction_splits():
    parts = decompose_task("write the report then send it to the client")
    assert parts == ["write the report", "send it to the client"]


def test_decompose_task_oxford_list_splits_into_three():
    parts = decompose_task("validate the input, sanitize the output, and log the result")
    assert len(parts) == 3
    assert parts == ["validate the input", "sanitize the output", "log the result"]


def test_decompose_task_quoted_payload_double_quotes_never_split():
    task = 'Turn this into a brief: "export button does nothing on Safari; works on Chrome."'
    assert decompose_task(task) == [task.strip()]


def test_decompose_task_quoted_payload_curly_quotes_never_split():
    task = "Summarize this feedback: “the app crashes and loses my data”"
    assert decompose_task(task) == [task.strip()]


def test_decompose_task_single_clause_stays_one_step():
    task = "Build me a dashboard that shows my Stripe revenue"
    assert decompose_task(task) == [task.strip()]


def test_decompose_task_min_two_word_fragment_filter_drops_short_pieces():
    # "cats" and "dogs" are single-word fragments after the split and must be
    # dropped by the >=2-word filter, collapsing to the whole task instead.
    parts = decompose_task("cats and dogs")
    assert parts == ["cats and dogs"]


def test_decompose_task_prose_comma_is_not_split():
    task = "My React app re-renders too much, help me fix the performance"
    assert decompose_task(task) == [task.strip()]


def test_decompose_task_empty_string_returns_itself():
    assert decompose_task("") == [""]


# ---------------------------------------------------------------------------
# generate_trace
# ---------------------------------------------------------------------------


def _make_ir(**overrides) -> IR:
    defaults = dict(
        language="en",
        persona="assistant",
        role="test role",
        domain="software",
        output_format="markdown",
        length_hint="medium",
    )
    defaults.update(overrides)
    return IR(**defaults)


def test_generate_trace_minimal_ir_has_core_fields_only():
    ir = _make_ir()
    lines = generate_trace(ir)

    assert "language=en" in lines
    assert "persona=assistant" in lines
    assert "domain=software" in lines
    # No metadata was set, so optional sections must not appear.
    assert not any(line.startswith("risk_flags=") for line in lines)
    assert not any(line.startswith("domain_evidence:") for line in lines)
    assert not any(line.startswith("entities=") for line in lines)


def test_generate_trace_includes_metadata_driven_sections():
    ir = _make_ir(domain="security", tools=["shell", "browser"])
    ir.metadata = {
        "heuristic_version": "v2.0",
        "detected_domain_evidence": ["security:oauth", "security:jwt"],
        "summary": True,
        "summary_limit": 5,
        "variant_count": 2,
        "domain_confidence": 0.875,
        "domain_scores": {"security": 3, "software": 1},
        "risk_flags": ["destructive_operation"],
        "ambiguous_terms": ["optimize", "fast"],
        "clarify_questions": ["Which metric?"],
        "code_request": True,
        "pii_flags": ["email"],
        "domain_candidates": ["security", "software"],
        "entities": ["Kubernetes", "GPT-4"],
        "complexity": "high",
        "persona_evidence": {"scores": {"developer": 2, "mentor": 1}},
        "ir_signature": "abc123",
    }

    lines = generate_trace(ir)

    assert "heuristic_version=v2.0" in lines
    assert "domain=security (2 evid)" in lines
    assert "domain_evidence:security:oauth,security:jwt" in lines
    assert "summary=True" in lines
    assert "summary_limit=5" in lines
    assert "variant_count=2" in lines
    assert "domain_conf=0.88" in lines
    assert "domain_scores=security:3,software:1" in lines
    assert "tools=shell,browser" in lines
    assert "risk_flags=destructive_operation" in lines
    assert "ambiguous_terms=fast,optimize" in lines  # sorted alphabetically
    assert "clarify_q_count=1" in lines
    assert "code_request=True" in lines
    assert "pii_flags=email" in lines
    assert "domain_candidates=security,software" in lines
    assert "entities=Kubernetes,GPT-4" in lines
    assert "complexity=high" in lines
    assert "persona_scores=developer:2,mentor:1" in lines
    assert "ir_signature=abc123" in lines


def test_generate_trace_single_domain_candidate_is_omitted():
    ir = _make_ir()
    ir.metadata = {"domain_candidates": ["software"]}
    lines = generate_trace(ir)
    assert not any(line.startswith("domain_candidates=") for line in lines)


def test_generate_trace_is_deterministic_for_same_ir():
    ir = _make_ir()
    ir.metadata = {"domain_scores": {"b": 1, "a": 2}}
    assert generate_trace(ir) == generate_trace(ir)


# ---------------------------------------------------------------------------
# optimize_ir
# ---------------------------------------------------------------------------


def test_optimize_ir_dedupes_goals_and_tasks_by_first_60_chars():
    long_prefix = "a" * 60
    ir = _make_ir(
        domain="general",
        goals=[long_prefix + " tail one", long_prefix + " tail two (different ending)"],
        tasks=["short unique task one", "short unique task two"],
    )
    result = optimize_ir(ir)
    # Both goals share the same first-60-chars key, so only the first survives.
    assert result.goals == [long_prefix + " tail one"]
    assert result.tasks == ["short unique task one", "short unique task two"]


def test_optimize_ir_keeps_distinct_goals():
    ir = _make_ir(domain="general", goals=["first distinct goal", "second distinct goal"])
    result = optimize_ir(ir)
    assert result.goals == ["first distinct goal", "second distinct goal"]


def test_optimize_ir_injects_english_domain_baseline_for_coding():
    ir = _make_ir(domain="coding", language="en", constraints=["Keep it concise."])
    result = optimize_ir(ir)
    assert any(
        "type hints, docstrings" in c for c in result.constraints
    ), result.constraints


def test_optimize_ir_injects_turkish_domain_baseline_for_security():
    ir = _make_ir(domain="security", language="tr", constraints=[])
    result = optimize_ir(ir)
    assert any("En az ayrıcalık ilkesini uygula" in c for c in result.constraints)


def test_optimize_ir_does_not_duplicate_existing_baseline_constraint():
    baseline = "Include type hints, docstrings, and handle edge cases defensively."
    ir = _make_ir(domain="coding", language="en", constraints=[baseline])
    result = optimize_ir(ir)
    baseline_count = sum(1 for c in result.constraints if "type hints, docstrings" in c)
    assert baseline_count == 1


def test_optimize_ir_no_baseline_for_unknown_domain():
    ir = _make_ir(domain="general", language="en", constraints=["Be concise."])
    result = optimize_ir(ir)
    assert result.constraints == ["Be concise."]


def test_optimize_ir_marks_metadata_optimized():
    ir = _make_ir(domain="general")
    result = optimize_ir(ir)
    assert result.metadata["optimized"] is True
