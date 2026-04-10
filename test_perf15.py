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
COMBINED_INJECTION_PATTERN = re.compile("|".join(f"(?:{p})" for p in _INJECTION_RAW_PATTERNS), re.IGNORECASE)

text = "This is a normal prompt with no issues. " * 50

def original():
    safety_flags = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            safety_flags.append("PROMPT_INJECTION_RISK")
            break

def optimized():
    safety_flags = []
    if COMBINED_INJECTION_PATTERN.search(text):
        safety_flags.append("PROMPT_INJECTION_RISK")

print("Original:", timeit.timeit(original, number=100000))
print("Optimized:", timeit.timeit(optimized, number=100000))
