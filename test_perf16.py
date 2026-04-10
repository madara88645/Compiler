import re
import timeit

text = "This is a normal prompt with no issues. " * 50
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

def original():
    words = set(re.compile(r"\w+").findall(lower_text))
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


# Since most patterns do not contain spaces:
CONFLICT_PAIRS_SPACE = [
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

# Separate out terms with spaces so we don't have to check if " " in term every time
def setup_conflicts():
    optimized_pairs = []
    for a, b in CONFLICT_PAIRS:
        a_no_space = {t for t in a if " " not in t}
        a_space = {t for t in a if " " in t}
        b_no_space = {t for t in b if " " not in t}
        b_space = {t for t in b if " " in t}
        optimized_pairs.append((a_no_space, a_space, b_no_space, b_space, a, b))
    return optimized_pairs

OPT_PAIRS = setup_conflicts()

def optimized():
    words = set(re.compile(r"\w+").findall(lower_text))
    words_set = set(words)
    conflicts = []
    for a_no_space, a_space, b_no_space, b_space, group_a, group_b in OPT_PAIRS:
        if not a_no_space.isdisjoint(words_set):
            found_a = True
        else:
            found_a = False
            for term in a_space:
                if term in lower_text:
                    found_a = True
                    break
        if not found_a:
            continue

        if not b_no_space.isdisjoint(words_set):
            found_b = True
        else:
            found_b = False
            for term in b_space:
                if term in lower_text:
                    found_b = True
                    break

        if found_a and found_b:
            desc_a = next(iter(group_a))
            desc_b = next(iter(group_b))
            conflicts.append(f"{desc_a} vs {desc_b}")

    return conflicts

print("Original:", timeit.timeit(original, number=100000))
print("Optimized:", timeit.timeit(optimized, number=100000))
