import time
import operator
import math

test_str = "1234-5678-9012-3456 abc def ghi jkl"

# List comprehension
start = time.perf_counter()
for _ in range(100000):
    _ = [w.lower() for w in test_str.split() if len(w) > 2]
end = time.perf_counter()
print(f"List comp: {end - start:.6f}s")

# Explicit loop
start = time.perf_counter()
for _ in range(100000):
    c = []
    for w in test_str.split():
        if len(w) > 2:
            c.append(w.lower())
end = time.perf_counter()
print(f"Explicit loop: {end - start:.6f}s")
