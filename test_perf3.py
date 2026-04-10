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
lower_text = " ".join(words)

def test_original():
    weasel_count = 0
    for w in words:
        if w in WEASEL_WORDS:
            weasel_count += 1

    if "try to" in lower_text:
        weasel_count += 1
    if "kind of" in lower_text:
        weasel_count += 1
    if "sort of" in lower_text:
        weasel_count += 1
    return weasel_count

def test_optimized():
    # Intersection is very fast
    weasel_count = sum(1 for w in words if w in WEASEL_WORDS)
    if "try to" in lower_text:
        weasel_count += 1
    if "kind of" in lower_text:
        weasel_count += 1
    if "sort of" in lower_text:
        weasel_count += 1
    return weasel_count

def test_optimized2():
    weasel_count = len([w for w in words if w in WEASEL_WORDS])
    if "try to" in lower_text:
        weasel_count += 1
    if "kind of" in lower_text:
        weasel_count += 1
    if "sort of" in lower_text:
        weasel_count += 1
    return weasel_count


print("Original:", timeit.timeit(test_original, number=10000))
print("Optimized:", timeit.timeit(test_optimized, number=10000))
print("Optimized2:", timeit.timeit(test_optimized2, number=10000))
