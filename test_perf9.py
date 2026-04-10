import re
import timeit

def original(val):
    digits_count = sum(map(str.isdigit, val))
    return digits_count

def optimized(val):
    digits_count = sum(1 for c in val if c.isdigit())
    return digits_count

val = "1234-5678-9012-3456" * 10
print("Original map:", timeit.timeit(lambda: original(val), number=100000))
print("Gen expr:", timeit.timeit(lambda: optimized(val), number=100000))
