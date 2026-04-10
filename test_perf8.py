import re
import timeit

def original(text):
    lower = text.lower()
    return lower

def optimized(text):
    # The current code assigns `lower = text.lower()` and then uses `lower` everywhere.
    return text.lower()
