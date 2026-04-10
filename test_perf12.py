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

text = "Write a comprehensive detailed report but keep it brief and short." * 20
words = set(re.compile(r"\w+").findall(text.lower()))

def original():
    lower_text = text.lower()
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
            conflicts.append("a vs b")
    return conflicts

def optimized():
    lower_text = text.lower()
    conflicts = []
    for group_a, group_b in CONFLICT_PAIRS:
        if not group_a.isdisjoint(words):
            found_a = True
        else:
            found_a = False
            for term in group_a:
                if " " in term and term in lower_text:
                    found_a = True
                    break
        if not found_a:
            continue

        if not group_b.isdisjoint(words):
            found_b = True
        else:
            found_b = False
            for term in group_b:
                if " " in term and term in lower_text:
                    found_b = True
                    break

        if found_a and found_b:
            conflicts.append("a vs b")
    return conflicts

print("Original:", timeit.timeit(original, number=10000))
print("Optimized:", timeit.timeit(optimized, number=10000))
