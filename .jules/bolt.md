## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.
## 2024-08-08 - Use built-in str.split and join instead of re.sub for collapsing spaces
**Learning:** In Python, to optimize collapsing multiple consecutive whitespaces (spaces/tabs) into a single space, using `' '.join(text.split())` is significantly faster (~5-6x) than using a compiled regular expression like `re.sub(r'\s+', ' ', text).strip()`.
**Action:** Replace `re.sub(r'\s+', ' ', text).strip()` with `' '.join(text.split())` for collapsing spaces in Python strings.

## 2024-05-13 - Optimize Regex Whitespace Normalization
**Learning:** In Python, calling `re.sub` and `.strip()` has measurable overhead even if the target pattern (e.g. `[ \t]{2,}`) does not exist in the string. Using a fast substring `in` check (e.g. `"  " in ln or "\t" in ln`) before invoking the regex can skip the overhead for lines without multi-spaces or tabs, providing significant speedups (~2x faster) without altering Unicode handling semantics.
**Action:** When a regex search/replace is applied universally but only matches a subset of inputs (like whitespace collapsing), prepend a fast string inclusion check to short-circuit the regex call.
