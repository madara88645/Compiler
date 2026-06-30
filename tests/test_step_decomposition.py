"""Plan steps should decompose a coordinated request, not echo it verbatim.

The value benchmark found goals == tasks == the single plan step == the raw
sentence: no decomposition, the core reason to use the tool. build_steps now
splits a task on its own coordinating conjunctions ("and"/"then"/commas) into
sub-steps, without inventing any requirement the user did not state.
"""

from app.compiler import build_steps, compile_text_v2


def test_and_coordinated_task_splits():
    steps = build_steps(
        ["Write a Python function to parse nginx logs and detect brute-force login attempts"]
    )
    assert len(steps) >= 2


def test_comma_list_splits_into_three():
    steps = build_steps(
        ["Validate Stripe webhook signatures, enforce idempotency, and add focused tests"]
    )
    assert len(steps) == 3


def test_single_clause_task_stays_one_step():
    steps = build_steps(["Build me a dashboard that shows my Stripe revenue"])
    assert len(steps) == 1


def test_quoted_payload_is_never_split():
    # a quoted issue/example must stay coherent, not fragment on its punctuation
    steps = build_steps(
        [
            'Turn this GitHub issue into a brief: "export button does nothing on Safari; works on Chrome."'
        ]
    )
    assert len(steps) == 1


def test_prose_comma_is_not_split():
    steps = build_steps(["My React app re-renders too much, help me fix the performance"])
    assert len(steps) == 1


def test_decomposition_invents_no_new_words():
    task = "parse the access log and email a daily summary to the team"
    steps = build_steps([task])
    allowed = set(task.lower().replace(".", "").split())
    for step in steps:
        for word in step.lower().replace(".", "").split():
            assert word in allowed, f"invented word in step: {word!r}"


def test_compiled_plan_has_multiple_task_steps():
    ir = compile_text_v2(
        "Write a Python script that reads a log file, counts requests by IP, and flags noisy IPs"
    )
    task_steps = [s for s in ir.steps if getattr(s, "type", "task") == "task"]
    assert len(task_steps) >= 2
