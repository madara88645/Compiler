## 2025-04-25 - [Precomputing Inverse Document Frequency (IDF)]
**Learning:** In the Simple Index RAG module (`app/rag/simple_index.py`), calculating the TF-IDF for sentences happens iteratively within an inner loop inside `compute_tfidf` function which is called for each sentence against a `doc_freq` Counter. Re-calculating the IDF via `math.log` for the entire dataset inside the inner loop was an unnecessary computation overhead. Since the document count and total frequency mapping are static, these metrics can be pre-calculated upfront using a dictionary cache to allow O(1) lookups.
**Action:** Precompute static mapping dependencies inside tight inner loops with caching logic to mitigate unnecessary redundant execution overhead.


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

## 2025-03-09 - Avoiding Intermediate String Allocation for Pure Counting
**Learning:** In the PII scanning heuristics (`app/heuristics/__init__.py` and `app/heuristics/security.py`), logic was previously using `len(re.sub(r'[^0-9]', '', val))` to count the number of digits in a string. This executes the regex engine and allocates an entirely new string in memory just to determine its length. Replacing it with a native generator expression `sum(1 for c in val if c.isdigit())` avoids the regex overhead and memory allocation, achieving a ~4x to ~5x speedup in isolated benchmarks, while retaining the exact logic.
**Action:** When only needing to count occurrences of a simple character class (like digits or letters) in a string, avoid `re.sub` string creation. Use Python generator comprehensions like `sum(1 for c in val if c.isdigit())` instead to bypass memory allocations in hot paths like text scanning.

## 2024-03-30 - Optimize PII Masking and Set Comprehensions
**Learning:** In Python hot loops (like `app/heuristics/linter.py`), evaluating `any(p in text for p in group)` with a generator expression is significantly slower than using an explicit `for` loop with early exit `break`. Also, using `pattern.subn()` is faster than doing a `list(pattern.finditer(text))` pass followed by a `pattern.sub()` pass, as it avoids searching the string twice.
**Action:** When evaluating multiple boolean string matches in performance-critical code, use explicit loops to avoid generator overhead. When both detecting and replacing regex matches, use `.subn()` to perform the operation in a single C-level pass.

## 2026-03-22 - Fast Character Counting in Strings
**Learning:** In Python, replacing `sum(1 for c in text if c.isdigit())` with `sum(map(str.isdigit, text))` provides a ~3x performance boost. The generator expression executes a bytecode loop in Python, while `map` pushes the iteration entirely into C. Since `str.isdigit` returns booleans (which are integers `1` or `0` in Python), `sum()` seamlessly counts the matches.
**Action:** When counting occurrences of characters that match a string method (like `.isdigit()`, `.isalpha()`, `.isspace()`), use `sum(map(str.method, text))` for maximum performance in hot paths.

## 2025-03-09 - Pre-compiling Regex Patterns for Performance
**Learning:** In Python, iterating over uncompiled string patterns using `re.finditer(pattern, text)` repeatedly compiles the regex patterns on every call, leading to significant overhead in hot loops like security scanners.
**Action:** Always pre-compile regular expressions at the module level (e.g., `COMPILED_PATTERNS = {k: re.compile(v) for k, v in PATTERNS.items()}`) and use `.finditer` directly on the compiled objects to improve performance.

## 2025-03-09 - Pre-compiling Regex Patterns inside Repeated Methods
**Learning:** Defining dictionary maps or strings with regex patterns inside frequently called functions (like `_resolve_conflicts` or `_inject_reasoning`) causes Python to re-allocate structures and `re.search` to re-compile (or rely on internal limited LRU caches) each time.
**Action:** Move static regex definitions and lists of patterns to the module level, pre-compile them with `re.compile()`, and use the pre-compiled `.search()` or `.match()` methods inside the hot functions for a guaranteed speedup.

## 2026-03-24 - Optimizing String Tokens Membership Check
**Learning:** In Python, when checking for membership of multiple items in a tokenized string within a loop or comprehension (e.g., `[t for t in terms if t in text.split()]`), evaluating `.split()` inside the loop forces Python to allocate new lists and do O(N) membership checks repeatedly.
**Action:** Extract `.split()` outside the loop and convert it to a `set` (e.g., `words = set(text.split())`). This ensures the string is split only once and provides O(1) membership lookups for the inner evaluation, significantly improving performance especially for large texts.

## 2026-04-05 - Prevent Event Loop Blocking in FastAPI
**Learning:** In FastAPI, declaring an endpoint as `async def` while running a blocking synchronous operation (like SQLite I/O) directly within it blocks the main event loop, severely degrading concurrent performance.
**Action:** Declare endpoints performing blocking I/O as `def` instead of `async def`. FastAPI will automatically offload these synchronous endpoints to a separate threadpool, allowing the main event loop to remain non-blocking.

## 2024-05-18 - Schema Sanitizer Fast-Path Avoids Expensive Regex Loops
**Learning:** Pre-compiling regex substitutions at the module level and using a combined alternated regex (`re.search(r"A|B|C")`) to pre-filter text inside a hot loop is extremely effective when matches are rare. In `SchemaSanitizerHandler`, checking for 7 specific string fields using this pattern skips the expensive and repeated execution of 7 `re.sub` replacements on the vast majority of constraints where those fields do not exist.
**Action:** When applying multiple regex replacements (`re.sub` or `re.subn`) inside a loop over text, always evaluate if the target patterns can be combined into a fast-path alternated check to skip the replacement logic entirely when not needed. Pre-compile all regexes at the module level to avoid overhead.

## 2024-05-24 - Avoiding regex backtracking on fully concatenated text
**Learning:** In the `LogicAnalyzer` when searching for dependency rules, concatenating all sentences into a single `full_text` string and evaluating complex regular expressions with `re.DOTALL` against it created an exponential backtracking bottleneck on large prompts, adding tens of seconds to processing.
**Action:** Restrict regular expression evaluations to individual sentences wherever possible and avoid fully concatenating blocks of text to apply complex bounded regexes.

## 2024-05-30 - [Optimize re.match with strip in fence parsing]
**Learning:** Using `re.match` within tight parsing loops (like `_is_fence_close` which is called per line within token optimizer fence handling) can be disproportionately slow.
**Action:** When matching a homogeneous string prefix combined with full string equality (like checking if a line is exclusively composed of a specific character length `N` or more), use `str.startswith(prefix) and not str.strip(char)` instead. It avoids regex compilation and execution overhead and was measured to be ~7x faster.

## 2024-05-30 - Pre-compiling dictionary iteration patterns
**Learning:** Iterating over a dictionary of string patterns and compiling them with `re.escape` and string concatenation inside a loop before passing to `re.findall` causes unnecessary string allocations and cache lookups (or cache misses/evictions if the regex cache is full), significantly degrading performance.
**Action:** When a method loops over a static dictionary of keyword-to-pattern mappings (e.g., `IMPLIED_PERSONAS`), pre-compile the dictionary into `{re.compile(pattern): value}` at the class `__init__` or module level, and iterate over the pre-compiled regex objects in the hot path. This can yield ~1.7x performance improvements for regex matching tasks.

## 2026-05-19 - Fast JSON Parsing for Embeddings
**Learning:** Using `json.loads` to repeatedly parse vector embeddings stored as JSON strings in the database creates a major CPU bottleneck due to the sheer number of floats being deserialized during a similarity search loop.
**Action:** Always prefer `orjson.loads` over the standard `json.loads` module when deserializing large arrays of floats or when executing JSON parsing on a hot path. `orjson` executes entirely in C and parses float arrays ~10x to 15x faster than standard `json`.

## 2025-04-12 - Ensure runtime imports for fast library drop-ins
**Learning:** When dropping in faster external libraries like `orjson` to replace standard library equivalents (like `json`), it is easy to forget the import statement if the standard library is already imported elsewhere in the module. This leads to `NameError` at runtime.
**Action:** Always manually `grep` for the exact `import <new_library>` statement in the modified file to ensure it exists before submitting.

## 2026-05-24 - Avoiding regex backtracking on fully concatenated text
**Learning:** In the `LogicAnalyzer` when searching for dependency rules, evaluating complex regular expressions containing greedy components like `(.+?)` against text created an exponential backtracking bottleneck on large prompts, adding tens of seconds to processing.
**Action:** Restrict regular expression evaluations to individual sentences wherever possible, and implement a fast-path alternated regex check (using simple `\b(?:word1|word2)\b` boundaries) to skip the expensive regex execution entirely on strings where dependency keywords are not present.

## 2026-05-19 - Replacing any(...) generator expressions
**Learning:** In Python performance-critical paths, replacing `any(...)` generator expressions with an explicit `for` loop inside a helper function (e.g., `_contains_any`) significantly improves short-circuiting speed by avoiding generator initialization overhead, while maintaining readability.
**Action:** When evaluating multiple boolean string matches in performance-critical code where the expression is evaluated many times, use explicit loops inside helper functions to avoid generator overhead.

## 2024-05-20 - Fast JSON Serialization in SQLite Hooks
**Learning:** In paths that serialize and deserialize large dicts frequently (like reading/writing `HistoryEntry` metadata to/from SQLite in `HistoryManager`), using `orjson.loads` and `orjson.dumps` is dramatically faster (up to ~8-10x) than the standard library `json` module.
**Action:** When working on DB hooks or large payload serialization, use `orjson` instead of `json`, keeping in mind that `orjson.dumps()` returns bytes and must be `.decode('utf-8')` if a string is needed for the database insert.

## 2024-05-30 - Regex Precompilation in RAG Parsers
**Learning:** In text parsing hot paths, such as the `parse_html` function in `app/rag/parsers.py` used during document ingestion, creating regex pattern objects on the fly with inline regex literals introduces significant, recurring overhead. Pre-compiling the regex objects using `re.compile()` at the module level avoids redundant compilation on every function call, resulting in a ~10x speedup for pattern substitution.
**Action:** Always extract static regular expression patterns to module-level constants using `re.compile()` if they are used within frequently executed functions or hot paths like parsers, tokenizers, or loops.

## 2024-05-30 - Replace re.sub with str.replace for literal strings
**Learning:** In Python, using `re.sub(pattern, var_value, result)` to replace literal substrings (like `{{var_name}}`) is unnecessarily slow due to regex engine overhead and compilation, even if `re.escape` is used. Furthermore, if `var_value` happens to contain regex backreferences (like `\1`), `re.sub` can throw errors or behave unexpectedly.
**Action:** When replacing known literal strings or templates in a tight loop, always prefer the built-in `str.replace(target, value)`. It is nearly 2x faster for these operations. Use Python f-string escaping (e.g., `f"{{{{{var_name}}}}}"`) to easily generate strings containing literal `{` and `}` characters.

## 2026-05-25 - Python 3.12 math.sumprod for Vector Dot Products
**Learning:** In Python 3.12+, `math.sumprod` is implemented in C and provides superior performance for calculating dot products of vectors compared to `sum(map(operator.mul, a, b))`. Microbenchmarks show `math.sumprod` is over 3x faster than `sum(map(...))`.
**Action:** When performing local dot product similarity calculations or sum-of-products in Python 3.12+, always use `math.sumprod` instead of `sum(map(operator.mul))` or list comprehensions to significantly improve CPU utilization and performance during vector operations.
## 2024-05-14 - Fast subset matching with isdisjoint()

**Learning:** When checking if any elements from an iterable exist in a set in Python, the `not my_set.isdisjoint(iterable)` method is significantly faster (5-10x) than the equivalent `any(item in my_set for item in iterable)` generator expression, as it is implemented natively in C and avoids generator overhead.

**Action:** Whenever checking for overlaps between a set and a list/iterable in performance-critical paths, always use `not my_set.isdisjoint(iterable)` instead of `any()`.

## 2024-05-14 - Fast substring checking with helper functions

**Learning:** Replacing an inline `any(keyword in text for keyword in keywords)` generator expression with a standard loop inside a fast-path helper function (like `_contains_any_keyword(text, keywords)`) yields a 3-4x performance improvement by avoiding the initialization overhead of generator objects in hot paths.

**Action:** Continue replacing `any()` expressions used for substring searches with module-level `_contains_any` helper functions in performance-sensitive text analysis modules like the heuristics handlers. Always verify that the helper function is properly imported and exported in the `__init__.py` or utility file.

## 2024-05-18 - Replacing small generator expressions with explicit loops
**Learning:** In Python, using `any()` combined with a generator expression over a small, statically sized tuple (e.g., iterating through exactly 4 pre-defined regex pattern objects) incurs significant generator initialization and context setup overhead. An explicit unrolled `for` loop that performs the exact same short-circuit evaluation is observably faster for such localized hot paths.
**Action:** When short-circuiting over a small static collection of checks in a performance critical or frequently executed method, use an explicit `for` loop rather than `any(x for x in ...)` to bypass generator overhead.

## 2024-05-30 - Hoisting expensive loop math
**Learning:** In the `simple_index.py` TF-IDF implementation, executing `math.log` to calculate IDF inside the inner `for` loop for every sentence evaluation causes significant overhead because the same tokens are evaluated repeatedly.
**Action:** When a loop computes mathematical properties derived from a static corpus (like document frequency), pre-compute the properties into a cache dictionary *outside* the loop (e.g., `idf_cache`). Always remember to include a fallback/default value calculation (e.g., `idf_cache.get(tok, default_idf)`) inside the loop to avoid `KeyError` regressions for unseen elements.

## 2024-06-11 - Two-Step Vector Similarity Search Optimization
**Learning:** For large-scale vector similarity searches in SQLite without specialized extensions, fetching `content` alongside `vec` in the first pass creates a major memory and I/O bottleneck when the `content` payload is large, as it must be loaded for every vector only to be discarded when not in the top K.
**Action:** Implement a two-step retrieval method: fetch only the `chunk_id` and `vec` initially to calculate similarities and find the top K results. Then, execute a separate batch query to retrieve the full metadata (like `content` and `path`) only for the top K `chunk_id`s. This minimizes I/O and memory usage by avoiding broad scans of large text fields.

## 2024-05-24 - Fast Set Intersection for Filtering
**Learning:** In Python, replacing a list comprehension used to filter elements based on membership in a predefined set (e.g., `[term for term in MY_SET if term in words]`) with a direct set intersection (e.g., `list(MY_SET.intersection(words))`) pushes the iteration and comparison logic down to C level. In microbenchmarks within the validator, this resulted in a ~35% performance improvement for string matching tasks.
**Action:** Always prefer native set operations (like `.intersection()` or `&`) over list comprehensions or `for` loops when finding common elements or filtering against a set of known keywords, especially in high-frequency validation checks.
