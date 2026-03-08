## 2024-05-21 - tiktoken get_encoding performance bottleneck
**Learning:** `tiktoken.encoding_for_model` and `tiktoken.get_encoding` have internal caching but still incur measurable overhead (dictionary lookups, etc) when called repeatedly in high-frequency loops like token counting during prompt optimization, causing a performance bottleneck.
**Action:** Use a simple module-level dictionary cache for the encoder object to bypass `tiktoken`'s retrieval overhead, improving token counting performance.
