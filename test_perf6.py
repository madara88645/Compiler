import timeit

def original(text):
    lower_text = text.lower()
    return lower_text

def optimized(text):
    # What else could we do?
    return text.lower()
