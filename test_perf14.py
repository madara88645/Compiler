import re
import timeit

PII_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("IBAN", re.compile(r"\bTR\d{24}\b", re.IGNORECASE)),
]

text = "This is a normal prompt without PII. " * 50

def original():
    masked_text = text
    safety_flags = []
    for label, pattern in PII_PATTERNS:
        masked_text, count = pattern.subn(f"[{label}]", masked_text)
        if count > 0 and f"PII_{label}" not in safety_flags:
            safety_flags.append(f"PII_{label}")

def optimized():
    masked_text = text
    safety_flags = []
    for label, pattern in PII_PATTERNS:
        if pattern.search(masked_text):
            masked_text, count = pattern.subn(f"[{label}]", masked_text)
            if f"PII_{label}" not in safety_flags:
                safety_flags.append(f"PII_{label}")

print("Original:", timeit.timeit(original, number=10000))
print("Optimized:", timeit.timeit(optimized, number=10000))
