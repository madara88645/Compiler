import time
import operator
import math

test_str = "1234-5678-9012-3456"

# sum(map())
start = time.perf_counter()
for _ in range(100000):
    _ = sum(map(str.isdigit, test_str))
end = time.perf_counter()
print(f"sum(map): {end - start:.6f}s")

# Explicit loop
start = time.perf_counter()
for _ in range(100000):
    c = 0
    for ch in test_str:
        if ch.isdigit():
            c += 1
end = time.perf_counter()
print(f"Explicit loop: {end - start:.6f}s")
