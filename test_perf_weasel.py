import time
import operator
import math

words = ["maybe", "try", "to", "sort", "of", "briefly", "hello", "world", "fairly"] * 100
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

# map with __contains__
start = time.perf_counter()
for _ in range(10000):
    weasel_count = sum(map(WEASEL_WORDS.__contains__, words))
end = time.perf_counter()
print(f"map __contains__: {end - start:.6f}s")

# loop + count
start = time.perf_counter()
for _ in range(10000):
    c = 0
    for w in words:
        if w in WEASEL_WORDS:
            c += 1
end = time.perf_counter()
print(f"Explicit loop: {end - start:.6f}s")

# len intersection
start = time.perf_counter()
for _ in range(10000):
    weasel_count = len([w for w in words if w in WEASEL_WORDS])
end = time.perf_counter()
print(f"List comp len: {end - start:.6f}s")
