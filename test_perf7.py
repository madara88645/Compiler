import re
import timeit

WEASEL_WORDS = {
    # English
    "maybe",
    "try to",
    "sort of",
    "briefly",
    "somewhat",
    "fairly",
    "quite",
    "rather",
    "possibly",
    "apparently",
    "generally",
    "usually",
    "often",
    "sometimes",
    "kind of",
    "basically",
    "essentially",
    # Turkish
    "belki",
    "sanırım",
    "galiba",
    "muhtemelen",
    "biraz",
    "genellikle",
    "adeta",
    "gibi",
    "neyse",
}

words = ["this", "is", "a", "test", "with", "some", "words", "maybe", "try", "to", "sort", "of"] * 100

def original():
    weasel_count = 0
    for w in words:
        if w in WEASEL_WORDS:
            weasel_count += 1
    return weasel_count

def optimized():
    return sum(1 for w in words if w in WEASEL_WORDS)

def optimized_map():
    return len([w for w in words if w in WEASEL_WORDS])

def optimized_set():
    # Only counts unique weasel words
    pass

print("Original:", timeit.timeit(original, number=10000))
print("Gen Expr:", timeit.timeit(optimized, number=10000))
print("List Comp:", timeit.timeit(optimized_map, number=10000))
