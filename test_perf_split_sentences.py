import time
import operator
import math
import re

text = "This is a sentence. And another one! What about this? Dr. Smith said no. J. Doe agreed." * 1000

# Function logic
start = time.perf_counter()
for _ in range(100):
    pattern = r"(?<![A-Z][a-z]\.)(?<![A-Z]\.)(?<=\.|\?|!)\s+"
    sentences = re.split(pattern, text)
    _ = [s.strip() for s in sentences if s.strip()]
end = time.perf_counter()
print(f"Original: {end - start:.6f}s")

# Precompiled regex
start = time.perf_counter()
compiled_pattern = re.compile(r"(?<![A-Z][a-z]\.)(?<![A-Z]\.)(?<=\.|\?|!)\s+")
for _ in range(100):
    sentences = compiled_pattern.split(text)
    _ = [s.strip() for s in sentences if s.strip()]
end = time.perf_counter()
print(f"Precompiled: {end - start:.6f}s")
