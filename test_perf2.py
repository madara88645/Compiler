import re
import timeit

CONFLICT_PAIRS = [
    (
        {"detailed", "comprehensive", "thorough", "extensive", "deep"},
        {"brief", "concise", "short", "summary", "one-liner", "quick"},
    ),
    (
        {"json", "structured data", "yaml"},
        {"markdown", "prose", "narrative", "essay", "article"},
    ),
    (
        {"formal", "professional", "academic"},
        {"casual", "friendly", "informal", "slang", "chatty"},
    ),
    (
        {"step by step", "detailed explanation"},
        {"one-liner", "quick answer", "yes or no"},
    ),
]

text = "This is a brief text that does not contain any of the conflict patterns. " * 100
lower_text = text.lower()

def test_original():
    conflicts = []
    for group_a, group_b in CONFLICT_PAIRS:
        found_a = False
        for term in group_a:
            if term in lower_text:
                found_a = True
                break
        if not found_a:
            continue

        found_b = False
        for term in group_b:
            if term in lower_text:
                found_b = True
                break

        if found_a and found_b:
            desc_a = next(iter(group_a))
            desc_b = next(iter(group_b))
            conflicts.append(f"{desc_a} vs {desc_b}")
    return conflicts

def test_any():
    conflicts = []
    for group_a, group_b in CONFLICT_PAIRS:
        if any(term in lower_text for term in group_a) and any(term in lower_text for term in group_b):
            desc_a = next(iter(group_a))
            desc_b = next(iter(group_b))
            conflicts.append(f"{desc_a} vs {desc_b}")
    return conflicts

print("Original:", timeit.timeit(test_original, number=100000))
print("Any:", timeit.timeit(test_any, number=100000))
