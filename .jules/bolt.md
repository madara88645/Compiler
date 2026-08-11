## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-11 - Fast path string normalization
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs/newlines) into a single space, using `' '.join(text.split())` is significantly faster (~5x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`. `.split()` automatically handles all whitespace characters and removes leading/trailing empty elements.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
