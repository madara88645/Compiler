from app.heuristics import detect_live_debug


def test_detect_live_debug_true_cases():
    assert detect_live_debug("why is this failing") is True
    assert detect_live_debug("fix this error") is True
    assert detect_live_debug("traceback") is True


def test_detect_live_debug_false_cases():
    assert detect_live_debug("How do I write a Python function?") is False
    assert detect_live_debug("Explain quantum physics") is False
    assert detect_live_debug("") is False
