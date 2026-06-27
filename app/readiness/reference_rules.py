from __future__ import annotations

import re

# Well-known technologies that must NOT be flagged as unverifiable.
KNOWN_TECH = frozenset(
    {
        "aws",
        "gcp",
        "azure",
        "openai",
        "anthropic",
        "openrouter",
        "github",
        "gitlab",
        "docker",
        "kubernetes",
        "k8s",
        "postgres",
        "postgresql",
        "mysql",
        "sqlite",
        "mongodb",
        "redis",
        "react",
        "nextjs",
        "fastapi",
        "django",
        "flask",
        "express",
        "node",
        "nodejs",
        "python",
        "typescript",
        "javascript",
        "stripe",
        "vercel",
        "netlify",
        "cloudflare",
        "huggingface",
        "pytorch",
        "tensorflow",
        "langchain",
        "llamaindex",
        "supabase",
        "firebase",
    }
)

# "AcmeCloud SDK", "FooBar API", "Baz CLI" — a name followed by a product suffix.
# The name must start [A-Z][a-z] so all-caps acronyms (REST/JSON/HTTP) are NOT
# treated as product names ("REST API" is a generic phrase, not an unknown tool).
_SUFFIX_RE = re.compile(r"\b([A-Z][a-z][a-zA-Z0-9]*)\s+(SDK|API|CLI|Cloud|Platform|Service)\b")
# Standalone CamelCase product tokens like "AcmeCloud", "FooBarHub".
_CAMEL_RE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-zA-Z0-9]+)+)\b")


def detect_unverifiable_references(text: str) -> list[str]:
    found: list[str] = []
    for m in _SUFFIX_RE.finditer(text):
        name = m.group(1)
        phrase = f"{name} {m.group(2)}"
        if name.lower() not in KNOWN_TECH and phrase not in found:
            found.append(phrase)
    for m in _CAMEL_RE.finditer(text):
        tok = m.group(1)
        if tok.lower() in KNOWN_TECH:
            continue
        # Skip a bare token already covered by a suffix phrase, e.g. don't add
        # "AcmeCloud" when "AcmeCloud SDK" is already flagged.
        if any(tok in f for f in found):
            continue
        found.append(tok)
    return found[:5]
