import pytest

from app.heuristics import detect_browser_bug_report, detect_live_debug


@pytest.mark.parametrize(
    "prompt",
    [
        "why is this failing",
        "fix this error",
        "traceback",
    ],
)
def test_detect_live_debug_true_cases(prompt: str):
    assert detect_live_debug(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "canlı debug yap",
        "hata ayıkla lütfen",
        "yığın izi var",
        "canli debug",
        "istisna oluştu",
    ],
)
def test_detect_live_debug_turkish_true_cases(prompt: str):
    assert detect_live_debug(prompt) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "The download button is broken in Safari; help me fix it",
        "The page does not work in Firefox; help me fix it",
    ],
)
def test_detect_browser_bug_report_true_case(prompt: str):
    assert detect_browser_bug_report(prompt) is True


def test_detect_live_debug_false_cases():
    assert detect_live_debug("How do I write a Python function?") is False
    assert detect_live_debug("Explain quantum physics") is False
    assert detect_live_debug("My washing machine is broken; help me fix it") is False
    assert detect_live_debug("") is False


def test_detect_live_debug_ignores_substring_false_positives():
    # Keywords like "logs?" must not substring-match unrelated words such as
    # "login", "blog", "catalog", or "dialog" (regression for the missing
    # word boundaries in _JOINED_LIVE_DEBUG).
    assert detect_live_debug("Implement secure login sessions") is False
    assert detect_live_debug("write a blog post") is False
    assert detect_live_debug("browse the catalog") is False
    assert detect_live_debug("open the dialog box") is False


def test_detect_live_debug_matches_log_and_debug_keywords():
    # Genuine log/debug cues must still be detected once word boundaries are added.
    assert detect_live_debug("check the error log") is True
    assert detect_live_debug("attach the logs") is True
    assert detect_live_debug("help me debug this stack trace") is True


def test_detect_browser_bug_report_false_case():
    assert detect_browser_bug_report("My washing machine button is broken; help me fix it") is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Safari button works fine",
        "The download is broken in the kitchen",
        "Chrome page layout guide",
        "Firefox is not working for remote teams",
        "The button is broken in the UI mockup",
    ],
)
def test_detect_browser_bug_report_partial_marker_false_cases(prompt: str):
    assert detect_browser_bug_report(prompt) is False
