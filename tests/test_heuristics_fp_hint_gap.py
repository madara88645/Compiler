"""Direct unit coverage for app.heuristics._has_fp_hint_around_match: the
context-window scan that suppresses PII false positives (e.g. SSN/passport
patterns matched inside documentation examples). It is only exercised
indirectly today via detect_pii, so its own window-boundary and
case-sensitivity behavior has no direct assertions. High criticality — this
gates PII detection accuracy.
"""

from app.heuristics import _has_fp_hint_around_match


def test_hint_immediately_before_match_is_detected():
    text = "This is a sample 123-45-6789 in the docs"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_hint_immediately_after_match_is_detected():
    text = "Value 123-45-6789 is just a placeholder here"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_no_hint_anywhere_returns_false():
    text = "Contact John at 123-45-6789 for details"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is False


def test_hint_outside_default_window_is_not_detected():
    # "example" sits 30 chars before the match, past the default window of 24.
    prefix = "example " + ("x" * 22)
    match_val = "123-45-6789"
    text = prefix + " " + match_val
    start = text.index(match_val)
    end = start + len(match_val)
    assert _has_fp_hint_around_match(text, start, end) is False


def test_hint_just_inside_default_window_is_detected():
    # Place "format" exactly window(=24) chars before the match start.
    match_val = "123-45-6789"
    filler = "x" * 15
    prefix = "format " + filler  # len("format ") == 7, total 22 chars before match
    text = prefix + match_val
    start = text.index(match_val)
    end = start + len(match_val)
    assert start - text.index("format") <= 24
    assert _has_fp_hint_around_match(text, start, end) is True


def test_case_insensitive_hint_detection():
    text = "SAMPLE VALUE: 123-45-6789"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_custom_smaller_window_excludes_distant_hint():
    text = "This is a dummy value far away 123-45-6789 here"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    # With the default window(24) "dummy" (well outside 24 chars back) is not seen either,
    # but assert explicitly with a tiny window to make the boundary condition unambiguous.
    assert _has_fp_hint_around_match(text, start, end, window=2) is False


def test_zero_window_checks_only_the_matched_span_itself():
    # window=0 means lo=start, hi=end, so ctx is exactly the matched substring.
    text = "fake123456789xx"
    start = 0
    end = len(text)
    assert _has_fp_hint_around_match(text, start, end, window=0) is True


def test_zero_window_with_hint_just_outside_span_is_false():
    text = "fake 123456789xx"
    start = text.index("123456789xx")
    end = start + len("123456789xx")
    assert _has_fp_hint_around_match(text, start, end, window=0) is False


def test_hint_matches_as_substring_not_word_boundary():
    # "format" is substring-matched, so it fires inside "reformatted" too.
    text = "The reformatted value is 123-45-6789 shown below"
    start = text.index("123-45-6789")
    end = start + len("123-45-6789")
    assert _has_fp_hint_around_match(text, start, end) is True


def test_window_clamped_at_start_of_text_does_not_error():
    text = "123-45-6789 test data follows"
    start = 0
    end = len("123-45-6789")
    # window would push lo below 0; function must clamp to 0 and still find the hint after.
    assert _has_fp_hint_around_match(text, start, end, window=50) is True


def test_window_clamped_at_end_of_text_does_not_error():
    text = "example 123-45-6789"
    start = text.index("123-45-6789")
    end = len(text)
    # window would push hi past len(text); function must clamp and still find the hint before.
    assert _has_fp_hint_around_match(text, start, end, window=50) is True


def test_empty_text_with_zero_length_match_returns_false():
    assert _has_fp_hint_around_match("", 0, 0) is False
