import re
import timeit

text = "Write a comprehensive detailed report but keep it brief and short." * 20
lower_text = text.lower()

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

_WORD_PATTERN = re.compile(r"\w+")

def original():
    words = _WORD_PATTERN.findall(lower_text)
    words_set = set(words)
    conflicts = []
    for group_a, group_b in CONFLICT_PAIRS:
        if not group_a.isdisjoint(words_set):
            found_a = True
        else:
            found_a = False
            for term in group_a:
                if " " in term and term in lower_text:
                    found_a = True
                    break
        if not found_a:
            continue

        if not group_b.isdisjoint(words_set):
            found_b = True
        else:
            found_b = False
            for term in group_b:
                if " " in term and term in lower_text:
                    found_b = True
                    break

        if found_a and found_b:
            desc_a = next(iter(group_a))
            desc_b = next(iter(group_b))
            conflicts.append(f"{desc_a} vs {desc_b}")
    return conflicts

print("Original:", timeit.timeit(original, number=100000))
