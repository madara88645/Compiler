from app.compiler import compile_text

# Simple snapshot-like tests; if heuristics change intentionally,
# update expected subsets (not full strict equality to keep flexibility).

CASES = {
    "summary_case": "summarize abstract transformer tokenization outline",
    "cloud_case": "secure resilient cloud portfolio optimization this month",
}

# Expected minimal keys/conditions for stability
EXPECTED = {
    "summary_case": {
        "language": "en",
        "metadata.summary": "true",
        "domain_anyof": ["ai/nlp", "ai/ml", "general"],
    },
    "cloud_case": {
        "language": "en",
        "domain_anyof": ["cloud", "software", "general", "finance"],  # finance may appear due to 'portfolio' keyword
        "metadata.ambiguous_terms_contains": ["secure", "resilient"],
    }
}

def _get(d, path):
    cur = d
    for part in path.split('.'):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def test_snapshots_minimal():
    for name, text in CASES.items():
        ir = compile_text(text)
        data = ir.model_dump()
        exp = EXPECTED[name]
        assert data["language"] == exp["language"]
        domain = data["domain"]
        assert domain in exp["domain_anyof"], f"domain {domain} not in allowed {exp['domain_anyof']}"
        summary_flag = _get(data, "metadata.summary")
        if "metadata.summary" in exp:
            assert summary_flag == exp["metadata.summary"]
        terms = _get(data, "metadata.ambiguous_terms") or []
        needed = exp.get("metadata.ambiguous_terms_contains", [])
        for term in needed:
            assert term in terms, f"missing ambiguous term {term} in {terms}"
        # Ensure heuristic version and signature exist
        assert _get(data, "metadata.heuristic_version")
        assert _get(data, "metadata.ir_signature")
