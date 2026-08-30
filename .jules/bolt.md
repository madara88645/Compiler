## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-03-24 - Faster space collapsing in Python
**Learning:** `re.sub(r"\s+", " ", text)` is significantly slower (~5-6x) than using built-in string methods like `" ".join(text.split())` for collapsing consecutive whitespace. The built-in `.split()` handles all whitespace and empty drops implicitly.
**Action:** Prefer `str.split()` + `" ".join()` over regex for collapsing arbitrary whitespace in Python unless explicit regex matching constraints exist.
