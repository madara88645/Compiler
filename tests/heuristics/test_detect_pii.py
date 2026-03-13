from app.heuristics import detect_pii
import re
from unittest.mock import patch
import app.heuristics


def test_detect_pii_empty():
    assert detect_pii("") == []
    assert detect_pii("Hello world, no PII here.") == []


def test_detect_pii_email():
    text = "Contact me at test@example.com for more info."
    assert "email" in detect_pii(text)


def test_detect_pii_phone():
    # Valid international phone with spaces
    assert "phone" in detect_pii("Call me maybe +1 800 555 1234")
    # Valid phone, hyphenated
    assert "phone" in detect_pii("Or 555-123-4567 is good too")
    # Short phone should not be matched due to validation rule
    assert "phone" not in detect_pii("Just dial 12345")


def test_detect_pii_credit_card():
    # Valid 16 digit CC
    assert "credit_card" in detect_pii("My card is 1234-5678-9012-3456")
    # Valid 13 digit CC
    assert "credit_card" in detect_pii("1234567890123")
    # Short CC should not be matched due to validation rule
    assert "credit_card" not in detect_pii("My card is 1234-5678-9012")


def test_detect_pii_iban():
    # Turkish IBAN TR + 24 digits
    assert "iban" in detect_pii("Here is my IBAN TR123456789012345678901234")


def test_detect_pii_multiple():
    text = "Email test@example.com, phone 555-123-4567, and IBAN TR123456789012345678901234"
    result = detect_pii(text)
    assert "email" in result
    assert "phone" in result
    assert "iban" in result
    assert "credit_card" not in result


def test_detect_pii_max_flags():
    # Mock PII_PATTERNS locally to simulate more than 5 patterns to test the max limit
    mock_patterns = {
        "p1": re.compile(r"pattern1"),
        "p2": re.compile(r"pattern2"),
        "p3": re.compile(r"pattern3"),
        "p4": re.compile(r"pattern4"),
        "p5": re.compile(r"pattern5"),
        "p6": re.compile(r"pattern6"),
    }

    with patch.dict(app.heuristics.PII_PATTERNS, mock_patterns, clear=True):
        text = "pattern1 pattern2 pattern3 pattern4 pattern5 pattern6"
        result = app.heuristics.detect_pii(text)
        assert len(result) == 5
        assert "p6" not in result
