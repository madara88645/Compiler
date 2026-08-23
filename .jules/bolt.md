## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-23 - Fast string splitting
**Learning:** Built-in str.split() with no arguments is highly optimized in C to collapse arbitrary runs of whitespace and drop empty strings, making it ~4-5x faster than using a regular expression like `re.sub(r"[ \t]{2,}", " ", text).strip()` for whitespace normalization.
**Action:** When collapsing multiple whitespace characters into single spaces, prefer `" ".join(text.split())` over regular expressions unless specific complex matching is required.
