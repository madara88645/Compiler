## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.

## 2024-08-18 - Replacing `re.sub` with `str.split()` for whitespace collapsing
**Learning:** Using `re.sub(r"\s+", " ", text)` to collapse multiple whitespaces into a single space is significantly slower than using `" ".join(text.split())`, as `.split()` uses optimized C-based functions directly and handles all whitespace characters natively without the overhead of regex compilation and execution.
**Action:** When needing to collapse consecutive whitespaces into a single space, prefer `" ".join(text.split())` over `re.sub(r"\s+", " ", ...)` for improved performance.
