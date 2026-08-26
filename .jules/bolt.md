## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-05-18 - Fast string space collapsing
**Learning:** Python's built-in `str.split()` and `' '.join()` is significantly faster (~5-6x) than using `re.sub(r"\s+", " ", text)` for collapsing consecutive whitespaces into a single space because it utilizes highly optimized built-in C functions rather than the regex engine. `str.split()` automatically handles all whitespace characters (spaces, tabs, newlines) and removes leading/trailing empty elements.
**Action:** Replace `re.sub(r"\s+", " ", text)` with `' '.join(text.split())` for collapsing spaces when performance is a concern.
