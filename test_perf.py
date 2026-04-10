import re
import timeit

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*override", re.IGNORECASE),
    re.compile(r"forget\s+(?:everything|all)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:the\s+)?(?:above|previous)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]

_INJECTION_RAW_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions?",
    r"system\s*override",
    r"forget\s+(?:everything|all)",
    r"disregard\s+(?:the\s+)?(?:above|previous)",
    r"new\s+instructions?:",
    r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    r"jailbreak",
    r"DAN\s+mode",
]
COMBINED_PATTERN = re.compile("|".join(f"(?:{p})" for p in _INJECTION_RAW_PATTERNS), re.IGNORECASE)

text = "This is a very long text that does not contain any of the injection patterns. " * 100 + " jailbreak"

def test_list():
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            break

def test_combined():
    if COMBINED_PATTERN.search(text):
        pass

print("List:", timeit.timeit(test_list, number=10000))
print("Combined:", timeit.timeit(test_combined, number=10000))
