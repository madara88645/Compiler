import re
import timeit

PII_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("IBAN", re.compile(r"\bTR\d{24}\b", re.IGNORECASE)),
]

text = "This is my email test@example.com and my phone number is +1-555-555-5555. My IP is 192.168.1.1. My credit card is 1234-5678-9012-3456." * 10

def test_original():
    masked_text = text
    safety_flags = []
    for label, pattern in PII_PATTERNS:
        # Bolt Optimization: subn avoids finding matches twice
        masked_text, count = pattern.subn(f"[{label}]", masked_text)
        if count > 0 and f"PII_{label}" not in safety_flags:
            safety_flags.append(f"PII_{label}")

def test_optimized():
    masked_text = text
    safety_flags = []
    for label, pattern in PII_PATTERNS:
        # Avoid running replace if there's no match
        # search is generally faster than subn when there are no matches
        if pattern.search(masked_text):
            masked_text = pattern.sub(f"[{label}]", masked_text)
            if f"PII_{label}" not in safety_flags:
                safety_flags.append(f"PII_{label}")

def test_subn():
    masked_text = text
    safety_flags = []
    for label, pattern in PII_PATTERNS:
        masked_text, count = pattern.subn(f"[{label}]", masked_text)
        if count > 0:
             safety_flags.append(f"PII_{label}")

print("Original:", timeit.timeit(test_original, number=10000))
print("Optimized:", timeit.timeit(test_optimized, number=10000))
print("Subn:", timeit.timeit(test_subn, number=10000))
