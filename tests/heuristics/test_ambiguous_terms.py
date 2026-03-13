from app.heuristics import AMBIGUOUS_TERMS, detect_ambiguous_terms

def test_detect_ambiguous_terms_empty():
    """Test that an empty string returns an empty list."""
    assert detect_ambiguous_terms("") == []

def test_detect_ambiguous_terms_none_found():
    """Test that a string with no ambiguous terms returns an empty list."""
    assert detect_ambiguous_terms("Hello world! Write a python script.") == []

def test_detect_ambiguous_terms_single():
    """Test that a single ambiguous term is correctly identified."""
    assert "optimize" in AMBIGUOUS_TERMS
    result = detect_ambiguous_terms("Please optimize this code.")
    assert result == ["optimize"]

def test_detect_ambiguous_terms_multiple():
    """Test that multiple ambiguous terms are correctly identified."""
    assert "better" in AMBIGUOUS_TERMS
    assert "fast" in AMBIGUOUS_TERMS
    result = detect_ambiguous_terms("I want to make this better and fast.")
    assert sorted(result) == sorted(["better", "fast"])

def test_detect_ambiguous_terms_case_insensitive():
    """Test that terms are detected regardless of their case."""
    result = detect_ambiguous_terms("Make it MORE ROBUST.")
    assert result == ["robust"]

def test_detect_ambiguous_terms_multi_word():
    """Test multi-word ambiguous terms are detected."""
    assert "scalable architecture" in AMBIGUOUS_TERMS
    assert "optimize costs" in AMBIGUOUS_TERMS
    result = detect_ambiguous_terms("We need a scalable architecture to optimize costs.")
    # Note: "optimize" and "scalable" are also in AMBIGUOUS_TERMS and will match as substrings
    assert "scalable architecture" in result
    assert "optimize costs" in result
    assert "optimize" in result
    assert "scalable" in result

def test_detect_ambiguous_terms_substring():
    """Test that substring matches are detected (as per current implementation)."""
    # The current implementation checks `if t in lower`
    # which matches substrings. Let's write a test confirming this behavior.
    assert "fast" in AMBIGUOUS_TERMS
    result = detect_ambiguous_terms("I eat breakfast every day.")
    assert result == ["fast"]
