> **Read first:** [instructions.md](./instructions.md). Past learnings only — do not apply repo-wide without a task-specific reason.

## 2024-05-24 - Pre-calculate constraints to avoid repeated getattr in logic handler
**Learning:** In nested loops where `getattr(obj, "attr", default)` or type checks like `isinstance(obj, dict)` are executed heavily (e.g., matching constraints against multiple Regex patterns), it is significantly faster to hoist the attributes into a pre-calculated parallel list. This transforms $O(M \times N)$ lookups into $O(N)$ lookups. However, when the original list might be modified mid-loop, use slice assignment (`c_texts[:] = ...`) to keep the parallel lists strictly synced with the underlying objects.
**Action:** Before optimizing nested loops, identify properties fetched via `getattr` and hoist them into parallel lists or dictionaries prior to loop entry, ensuring to keep them synchronized if the source data structure undergoes deletion. Always maintain the same fallback access pattern (e.g., `getattr(obj, 'attr', default)`) to prevent `AttributeError` on missing attributes during optimization.

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

## 2024-05-30 - O(N) Tallying over O(N*M) List Comprehensions
**Learning:** In `app/compare.py`, filtering the same list of objects repeatedly using a list comprehension inside a loop over categories (`[i for i in issues if i.category == category]`) creates an O(N*M) operation that degrades performance as the number of issues scales.
**Action:** To optimize counting or grouping objects by category in Python, avoid iterating over predefined categories and using list comprehensions to filter items. Instead, use a single O(N) pass over the items to tally counts directly into a dictionary.

## 2024-05-30 - Combining List Comprehensions
**Learning:** In `app/heuristics/handlers/logic.py`, using multiple consecutive list comprehensions to extract different properties (e.g. `text` and `priority`) from the same list of objects iterates over the list multiple times, introducing redundant overhead.
**Action:** When extracting multiple separate properties from the same list of objects in Python, use a single explicit `for` loop to append to multiple lists simultaneously rather than executing multiple consecutive list comprehensions. This avoids redundant O(N) iterations and reduces overhead.

## 2024-05-31 - Fusing Multiple Tallying Generators
**Learning:** In Python, computing multiple aggregated values (like `tr_score` and `en_score`) over the same list using separate `sum(1 for x in list if ...)` generator expressions creates a major overhead. It forces the interpreter to re-iterate the list multiple times and incurs the initialization cost of generator objects for every call.
**Action:** When calculating multiple tallies over the same iterable, replace separate `sum()` generator expressions with a single explicit `for` loop. This bypasses Python generator initialization overhead, eliminates redundant O(N) iterations, and in benchmarks executed 2.5x to 3x faster.
## 2026-05-30 - O(N+M) set disjoint checking over O(N*M) any() expression
**Learning:** In Python, using `any(x in list_a for x in list_b)` inside a loop over many objects incurs massive O(N*M) list traversals combined with generator overhead. By converting the lookup keys to a set outside the loop (`tags_set = set(tags)`) and replacing the `any()` condition with the `tags_set.isdisjoint()` native method, we push the loop entirely to C-level set intersections, dramatically improving performance (benchmarked 5-10x speedup in large list filtering).
**Action:** When filtering objects using a check for "any overlapping element", use `set.isdisjoint` rather than nested list comprehensions or `any()` generator expressions.

## 2026-05-30 - Removing any() overhead with helper functions
**Learning:** Even simple boolean generator checks like `any(kw in text for kw in keywords)` are substantially slower than extracting the loop into a standalone method that uses a standard `for` loop with early `return True` logic. The overhead of creating generator context frames in Python is significant in hot loops.
**Action:** Replace `any()` boolean generators used for substring checks with fast-path loops in helper methods in performance-critical code.

## 2026-05-31 - Removing any() generator overhead in short-circuit evaluations
**Learning:** In highly recurrent loops (like PII detection or scanning windows), using an inline `any(hint in ctx for hint in hints)` expression creates a measurable performance bottleneck. The overhead of setting up and tearing down the generator frame eclipses the cost of the actual string `in` operation, especially for small sequences.
**Action:** Replace `any()` generator expressions used for substring matching in hot paths with explicit `for` loops to bypass generator overhead and achieve a 30-40% speedup.

## 2024-05-31 - Replacing small generator expressions with explicit loops does not improve readability
**Learning:** While replacing `any(x in list)` with a standard unrolled `for` loop avoids generator setup overhead and is technically faster at the CPython level, replacing concise and idiomatic generator expressions (like `any()` or `sum()`) often harms code readability and maintainability for negligible gain. The time saved per iteration is measured in nanoseconds, which doesn't resolve actual system bottlenecks (I/O, database fetching, large matrix math). Code reviewers consider this an unhelpful micro-optimization that violates clean code principles.
**Action:** Do not sacrifice the concise readability of built-in generators (`any()`, `all()`, `sum()`) by replacing them with verbose 5-6 line `for` loops unless the loop runs millions of times on the hot path (like tokenizer parsers) where overhead actually becomes a measurable bottleneck.
## 2024-05-31 - Fast Set creation for O(1) membership lookups over nested any() loops
**Learning:** In Python, replacing an O(N*M) nested lookup in list comprehension `[kind for kind in collection1 if any(item.kind == kind for item in collection2)]` with an O(N) approach by pre-computing a set of the attributes `item_kinds = {item.kind for item in collection2}` and then filtering via `[kind for kind in collection1 if kind in item_kinds]` provides massive speedups by leveraging O(1) set membership lookups in C, compared to repeatedly evaluating a Python generator expression.
**Action:** Always prefer pre-computing sets for membership testing to eliminate nested loop/generator lookups on object attributes when filtering lists.
## 2026-05-22 - Fast regex compilation in hot paths
**Learning:** In heavily utilized text processing functions like RAG chunkers, precompiling regular expressions at the module level (`re.compile(pattern)`) and calling `pattern.split(text)` is significantly faster than dynamically invoking `re.split(pattern, text)` because it avoids the overhead of implicit string concatenation, `re.split`'s internal caching lookup, and potential cache misses on every single function call.
**Action:** When a regular expression is executed thousands of times, such as when splitting large texts during document chunking, define the pattern as a module-level constant (e.g., `_SENTENCE_SPLIT_PATTERN = re.compile(...)`) instead of dynamically compiling or evaluating it inside the function.
## 2024-05-23 - Dictionary 'in' check beats .get() for sparse vector loops
**Learning:** When calculating dot products for sparse vectors stored as dictionaries, using the native `in` operator combined with direct key access (`if k in v2: dot += v * v2[k]`) is about 10% faster than using `v2.get(k, missing)` with a sentinel object. The method call overhead of `.get()` and checking `is not missing` in Python is higher than executing the native `COMPARE_OP` and `BINARY_SUBSCR` bytecodes.
**Action:** When computing dot products or intersectional values across dictionaries in tight loops, iterate over the smaller dictionary and use the `in` operator to check existence in the larger dictionary instead of using `.get()`.

## 2024-05-31 - Avoiding test suite collection failures
**Learning:** Running `make test-backend` may attempt to collect tests in the entire repository, including optional integration directories (like `integrations/mcp-server`) that might lack installed dependencies, causing the test suite to fail immediately.
**Action:** When running core backend tests, always use `python -m pytest tests/` rather than `make test-backend` to ensure only the core tests are executed and avoid collection errors from optional modules.

## 2026-06-25 - Removing any() generator overhead in heuristic short-circuit evaluations
**Learning:** In heavily utilized heuristic handlers (like `format_enforcer` and `paradox_resolver`), using an inline `any(c.text == val for c in constraints)` generator expression creates a measurable performance bottleneck. The overhead of setting up and tearing down the generator frame eclipses the cost of the actual string `==` operation, especially for small sequences like the current list of constraints. Microbenchmarks show a ~2x performance improvement by replacing it with an explicit loop.
**Action:** Replace `any()` generator expressions used for constraint existence checks in hot paths with explicit `for` loops to bypass generator overhead and achieve a 2x speedup.
## 2025-02-27 - CPython sum(map) vs List Comprehension Memory Performance
**Learning:** For counting elements matching a condition in CPython, `sum(map(condition_func, iterable))` evaluates largely at the C-level and requires O(1) extra memory, making it notably more memory-efficient and marginally faster than an equivalent list comprehension `len([x for x in iterable if condition])`, which materializes a full intermediate list requiring O(N) memory allocation.
**Action:** Replace length checks of filtered list comprehensions with `sum(map(...))` when optimizing for memory and tight CPU loops, particularly in hot heuristic or parsing paths.
## 2024-05-31 - Persistent HTTP Clients over Ephemeral Connections
**Learning:** Recreating HTTP clients (like `httpx.Client`) for every API request using a short-lived `with httpx.Client(...) as client:` context manager incurs massive overhead (up to 100x slower) because it forces a new TCP connection and TLS handshake for every call.
**Action:** When making synchronous API requests inside a class or frequently called function, initialize a persistent `httpx.Client` instance at the class level and reuse it across requests to benefit from HTTP connection pooling (Keep-Alive). Ensure to implement a `.close()` method to clean up resources appropriately.

## 2026-06-09 - Pre-compiling Regex Patterns inside Logic Analyzers
**Learning:** In text parsing hot paths, such as the `_split_sentences` function in `app/heuristics/logic_analyzer.py` used during prompt logic evaluation, creating regex pattern objects on the fly with inline `re.sub(r"pattern", ...)` introduces significant, recurring compilation overhead. Pre-compiling the regex objects using `re.compile()` at the module level avoids redundant compilation on every function call.
**Action:** Always extract static regular expression patterns to module-level constants using `re.compile()` if they are used within frequently executed logic analyzers and split functions.
## 2024-06-25 - Python regex match counting: findall vs finditer generator
**Learning:** In Python, using `sum(1 for _ in pattern.finditer(text))` to count regex matches is significantly slower than `len(pattern.findall(text))`. The generator expression introduces Python bytecode execution overhead for every match yielded, whereas `findall()` executes entirely in optimized C code to produce the list, achieving a ~3.5x speedup in microbenchmarks for typical string lengths.
**Action:** When counting occurrences of a regular expression, always use `len(pattern.findall(text))` instead of a generator expression with `sum()` and `finditer()`, unless memory usage from huge return lists is a strict constraint.

## 2024-05-18 - C-level Map, Zip, and Islice for Sequence Pairs
**Learning:** When generating overlapping string pairs from a list (e.g., combining adjacent sentences), replacing a manual `for` loop that uses `list.append` and string concatenation with `list.extend(map(" ".join, zip(seq, itertools.islice(seq, 1, None))))` shifts execution entirely to C. In our heuristics logic analyzer, this provided a 35%+ speedup by avoiding Python bytecode loop overhead.
**Action:** Always prefer `zip` with `itertools.islice` combined with `map` or list comprehensions for sliding window or adjacent element operations over manual `for` loop indexing.

## 2024-05-31 - Maintaining functional parity during Regex optimizations
**Learning:** When refactoring dynamic regex replacements (`re.sub`) to use pre-compiled patterns (`pattern.sub`) to avoid recompilation overhead in tight loops, it is critical to observe the default behaviors of the arguments. Python's `re.sub` replaces *all* occurrences by default. Adding an explicit `count=1` when migrating to `pattern.sub` will inadvertently change the behavior from global replace to single replace, introducing a functional regression while trying to optimize for speed.
**Action:** When migrating `re.sub` calls to `pattern.sub` for performance, strictly maintain the original arguments (specifically avoiding adding limits like `count=1` unless it was present originally) to ensure performance optimizations don't break existing functionality.


## 2024-06-22 - Optimize regex finditer loops by eliminating inner-loop conditionals
**Learning:** When using `pattern.finditer()` just to count matches and capture the first match's start index, putting a conditional check `if first_match_start < 0:` inside the loop forces an evaluation on every single match. Fetching the first element with `next(iterator, None)` and then summing the rest of the iterator avoids the inner-loop conditional branch entirely and provides a slight performance benefit without the memory overhead of `findall`.
**Action:** When iterating over regex matches to find the first position and the total count, avoid checking for the first element inside the loop. Use `first_match = next(matches, None)` and count the rest with `sum(1 for _ in matches)`.

## 2025-02-18 - Replacing finditer inner loop check with findall + len() for regex occurrence counting
**Learning:** When using regex pattern.finditer() to count matches and extract the first match index in a tight loop, checking the first iteration (`next(matches)`) and then looping over the rest of the iterator (`1 + sum(1 for _ in matches)`) introduces significant Python bytecode overhead. Using `pattern.findall()` to check and count occurrences (`len(matches)`), followed by a `pattern.search()` just for the start index, actually runs entirely in C and avoids iterator overhead, executing ~2x faster in Python.
**Action:** When counting regex match occurrences in hot paths (like heuristic keyword detection loops) and retrieving the first occurrence index, prefer `findall()` to check and count (`len()`), and fallback to `search()` for the first index, rather than manual `finditer` summation.
## 2024-05-31 - Replace any() generator expressions with explicit loops for fnmatch/string existence checks in PR safety analyzer
**Learning:** In code executed frequently across many elements (such as `_matches_any_pattern` in `path_rules.py` checking glob patterns against files, or `analyzer.py` checking test names and missing scope terms), the overhead of Python's generator expression within `any()` can cause micro-inefficiencies. Replacing `any(...)` with an explicit `for` loop avoids setting up the generator frame and executes slightly faster.
**Action:** When validating string existence or glob matching in paths that process many iterations, prefer an explicit loop with early return over generator expressions in `any()`.
## 2024-06-30 - Removing any() generator overhead in hot string matching functions
**Learning:** In frequently executed classification or parsing functions (like `emit_expanded_prompt` or `_scenario_considerations` in `app/emitters.py`), using `any(marker in text for marker in markers)` creates measurable performance overhead. The cost of setting up and tearing down the Python generator frame for every call outweighs the string search itself. Replacing the generator expression with a dedicated helper function (`_contains_any_marker`) that uses an explicit `for` loop achieves roughly a ~2x performance speedup in microbenchmarks.
**Action:** When performing simple string existence checks against an iterable of keywords in hot paths, prefer a fast-path helper function with an explicit `for` loop over `any()` with a generator expression.
## 2024-07-03 - Pre-compiled Combined Regex Patterns
**Learning:** Iterating over lists of compiled regular expressions and calling `.search()` on each one individually (e.g., `any(pattern.search(text) for pattern in patterns)`) introduces significant Python loop overhead. By combining these patterns using the regex OR operator (`|`) and compiling them into single patterns (`re.compile(r'\b(' + r'|'.join(patterns) + r')')`), the underlying C-based regex engine can process the text in a single pass. Microbenchmarks show this provides a ~3-5x performance speedup in heavily utilized heuristic analyzers.
**Action:** When checking a string against multiple potential regular expression patterns, prefer combining them into a single compiled pattern using the OR operator rather than iterating through a list of individual patterns.
## 2024-07-20 - Replacing generator expressions vs Algorithmic short-circuiting
**Learning:** When acting as Bolt, replacing idiomatic Python generator expressions (like `any()`) with explicit `for` loops is often considered an unmeasurable micro-optimization that sacrifices readability if done in isolation. However, if the logic can be structurally improved—such as using an early return to short-circuit and avoid executing an entire block of expensive operations (e.g., regex searches)—this constitutes a valid and measurable performance improvement.
**Action:** Focus on algorithmic improvements like early returns or short-circuiting before attempting micro-optimizations like removing generator overhead. Ensure that any code readability trade-offs are strictly justified by preventing the execution of expensive operations entirely.

## 2026-07-08 - Replace any() generator with `in` for exact list membership
**Learning:** In hot heuristic paths such as `detect_domain`, `any(ev == value for ev in evidence)` adds generator setup overhead for a simple exact-match check. Using `"value" in evidence` keeps the same semantics and avoids that overhead.
**Action:** Prefer the `in` operator over `any()` generator expressions when checking for an exact string in a list.

## 2025-03-05 - [Regex optimization over generator overhead]
**Learning:** Checking for regex matches across words iteratively inside an `any(...)` generator block is incredibly slow compared to a single C-optimized search call over the stripped text. `bool(_VOWEL_RE.search(text))` is >90x faster than `any(_VOWEL_RE.search(w) for w in words)`.
**Action:** Before iterating through tokens to match substrings against a regex, evaluate if the entire base string or text can be queried with `search` or `findall` directly to push the loop down to C-level regex code.
