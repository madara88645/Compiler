## 2024-05-24 - Optimizing PricingModel Cache Invalidation
**Learning:** Adding a short-circuit length check (`len(keys) != len(dict)`) before an O(N) set equality check (`set(keys) != dict.keys()`) helps only when the dictionary size changes (e.g., in tests/mocking). In the steady production state where lengths are equal, the code still builds a set from `keys_to_check` and compares it against the `dict.keys()` view; the length check then adds only a tiny constant overhead.
**Action:** Using `dict.keys()` directly in set comparisons avoids allocating an extra set for the right-hand side, since `dict_keys` already supports set operations. For further steady-state optimization, consider tracking a version integer or storing a frozenset of keys to avoid set creation entirely when `RATES` is unchanged.

## 2024-06-20 - Optimizing SQLite JSON Deserialization Cache Size
**Learning:** In the backend RAG implementation (`app/rag/simple_index.py`), embeddings are stored as JSON strings in an SQLite database. I initially attempted to optimize repeated deserialization by adding an `lru_cache` bounded to `maxsize=1024` for parsing these strings. However, because similarity searches involve a linear scan over all database chunks, if the database has more than 1,024 chunks, the cache is completely evicted during a single scan, resulting in a 0% cache hit rate on subsequent searches (cache thrashing).
**Action:** When caching objects that are iterated over sequentially during database table scans, ensure the cache boundary is sized large enough (e.g., `maxsize=65536`) to accommodate the entire dataset or use an unbounded cache if safe, otherwise the caching mechanism will only add overhead.

## 2024-07-26 - Fast Vector Dot Products in Python
**Learning:** For vector dot products in Python (without numpy), using `sum(map(operator.mul, vec_a, vec_b))` is approximately 30% to 40% faster than list comprehensions inside `sum([a * b for a, b in zip(vec_a, vec_b)])`. This is because it avoids the overhead of allocating an intermediate list in memory and pushes both iteration and multiplication to optimized C-level implementations.
**Action:** When calculating similarity scores or dot products on vectors represented as Python lists, always prefer `map(operator.mul, a, b)` wrapped in `sum()` over list comprehensions or generator expressions.

## 2024-08-14 - Optimizing Multiple Regex Pattern Matching Logic
**Learning:** When optimizing Python loops that count distinct regex pattern matches (e.g., `sum(1 for p in PATTERNS if re.search(p, text))`), joining all patterns into a single compiled regex (`re.compile('a|b').findall(text)`) introduces a functional regression because it counts the *total occurrences* of any pattern, not the *number of distinct patterns* matched.
**Action:** To safely optimize this logic while preserving exact functionality, pre-compile a list of distinct regular expressions at the module level and iterate through them: `sum(1 for r in COMPILED_REGEXES if r.search(text))`. Additionally, replace `re.search` with the native `in` operator (`p in text`) for exact string literals that don't rely on regex word boundaries, as it is significantly faster.

## 2026-03-18 - Optimizing Pattern Counting Logic
**Learning:** When trying to count how many distinct patterns match a given text (like `sum(1 for r in REGEXES if r.search(text))`), joining all patterns with `|` and using `re.findall()` then counting the distinct matches with `len(set())` avoids the overhead of executing multiple regex searches in a Python loop and delegates more work to the optimized C engine, offering a significant speedup while preserving the exact semantic of counting distinct pattern occurrences.
**Action:** When replacing a loop that counts distinct regex pattern matches (`sum(1 for r in COMPILED_REGEXES if r.search(text))`), use `len(set(re.compile('|'.join(PATTERNS)).findall(text)))` to avoid the loop overhead and get exactly the number of distinct patterns matched.

## 2026-03-22 - Safely Handling Monkeypatched Constants with Pre-compiled Caches
**Learning:** When pre-compiling dictionaries of regular expressions at the module level (e.g., `_COMPILED_PATS = {k: [re.compile(p) for p in v] for k, v in PATTERNS.items()}`), do not implement fragile runtime cache-invalidation logic (like checking list lengths or comparing first elements). Such logic adds overhead, risks `IndexError` on empty lists, and fails to invalidate if internal elements change.
**Action:** Simply iterate over the pre-compiled dictionary. If tests monkeypatch the original raw dictionary, modify those tests to explicitly `monkeypatch` the pre-compiled cache as well to ensure consistent test environments.

## 2025-03-09 - Pre-compiling Regex Patterns for Performance
**Learning:** In Python, iterating over uncompiled string patterns using `re.finditer(pattern, text)` repeatedly compiles the regex patterns on every call, leading to significant overhead in hot loops like security scanners.
**Action:** Always pre-compile regular expressions at the module level (e.g., `COMPILED_PATTERNS = {k: re.compile(v) for k, v in PATTERNS.items()}`) and use `.finditer` directly on the compiled objects to improve performance.

## 2025-03-09 - Catastrophic Backtracking Misdiagnosis and Bounded Regex Regressions
**Learning:** Replacing unbounded lazy matchers (`(.+?)`) with strictly bounded matchers (e.g., `([^.!?\n]{5,200}?)`) to "prevent catastrophic backtracking" in simple dependency parsing regexes (like `(.+?)\s+because\s+(.+)`) introduces severe functional regressions by failing to match short, valid clauses and altering newline handling originally enabled by `re.DOTALL`.
**Action:** Do not alter core regex semantics (length constraints or boundary characters) for performance unless you have proven exponential backtracking exists for that specific pattern architecture. Linear scanning overhead from simple `.+?` is generally acceptable and preferable to dropping valid matches.

## 2025-03-09 - The False Economy of Native String Matching Over Regex Boundaries
**Learning:** Attempting to optimize pre-compiled regex word-boundary checks (e.g., `\b(test|spec)\b`) by using native string substring matching (`any(w in text for w in ['test', 'spec'])`) introduces false positives (e.g., matching "latest" for "test"). Performance optimizations must perfectly preserve semantic boundaries.
**Action:** Always retain `re` for word boundary requirements. If optimizing a hot loop testing multiple boundary regexes, combine them into a single alternated pattern (`re.compile(r'\b(test|spec)\b')`) instead of falling back to loose native string matching.
