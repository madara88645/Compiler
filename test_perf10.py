import re
import timeit

words = ["this", "is", "a", "test", "with", "some", "words", "maybe", "try", "to", "sort", "of"] * 100
STOPWORDS = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "for", "to", "in", "of", "with"}

def original():
    informative_words = {w for w in words if w not in STOPWORDS and len(w) > 2}
    return len(informative_words)

def optimized():
    informative_words = 0
    seen = set()
    for w in words:
        if w not in seen and w not in STOPWORDS and len(w) > 2:
            seen.add(w)
            informative_words += 1
    return informative_words

def optimized2():
    # Set comprehension is actually fast, let's see
    pass

print("Original:", timeit.timeit(original, number=10000))
print("Optimized:", timeit.timeit(optimized, number=10000))
