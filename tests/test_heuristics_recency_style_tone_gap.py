from app.heuristics import detect_recency, extract_style_tone


# --------------------------------------------------------------------------
# detect_recency
# --------------------------------------------------------------------------


def test_detect_recency_true_for_today_keyword():
    assert detect_recency("What happened in the news today?") is True


def test_detect_recency_true_for_latest_keyword():
    assert detect_recency("Give me the latest release notes.") is True


def test_detect_recency_true_is_case_insensitive():
    assert detect_recency("BREAKING update on the merger") is True


def test_detect_recency_false_when_no_temporal_keyword_present():
    assert detect_recency("Write a function that reverses a string.") is False


def test_detect_recency_false_for_empty_string():
    assert detect_recency("") is False


# --------------------------------------------------------------------------
# extract_style_tone
# --------------------------------------------------------------------------


def test_extract_style_tone_detects_style_keywords():
    style, tone = extract_style_tone("Please write this in a structured, academic style.")
    assert "structured" in style
    assert "academic" in style
    assert tone == []


def test_extract_style_tone_detects_tone_keywords():
    style, tone = extract_style_tone("Keep the tone friendly and objective.")
    assert "friendly" in tone
    assert "objective" in tone
    assert style == []


def test_extract_style_tone_detects_turkish_keywords():
    style, tone = extract_style_tone("Resmi ve samimi bir dille yaz.")
    assert "resmi" in style
    assert "samimi" in tone


def test_extract_style_tone_returns_empty_lists_when_no_keywords_match():
    style, tone = extract_style_tone("Summarize the attached document.")
    assert style == []
    assert tone == []


def test_extract_style_tone_is_case_insensitive():
    style, tone = extract_style_tone("Use a CONCISE and FORMAL voice.")
    assert "concise" in style
    assert "formal" in tone
