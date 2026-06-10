## 2025-06-07 - Dictionary Comprehensions in Text Processing Loops
**Learning:** In heavily utilized Python text processing functions (like TF-IDF calculation in RAG chunkers), dictionary comprehensions execute significantly faster than manually populating a dictionary inside a `for` loop, as they leverage optimized C-level execution rather than running Python bytecode for each loop iteration.
**Action:** When populating dictionaries based on iterable data (especially from `collections.Counter`), use dictionary comprehensions instead of manual loops.
