# Compile Readiness Layer (Slice 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, no-LLM "request readiness" check to `/compile` that returns a `ready`/`clarify`/`risky`/`noise` verdict (plus clarification questions) before a model call is spent, and bundle two correctness fixes (Turkish→Turkish output, truthful mode label).

**Architecture:** New `app/readiness/` package mirrors `app/pr_safety/` (models + analyzer + rule module + markdown stub). `analyze_readiness()` is pure, offline, and reuses existing heuristics (`detect_risk_flags`, `detect_ambiguous_terms`, `generate_clarify_questions`, `detect_language`). The API attaches a `readiness` report to `CompileResponse` and applies a deterministic language guard that swaps a language-mismatched LLM render for the language-correct `emit_*_v2` render. The web compile screen shows a readiness banner and drops the unenforced "No hallucinations" label.

**Tech Stack:** Python 3.10+, pydantic, FastAPI, pytest (backend); Next.js, TypeScript, vitest (web).

**Conventions for every task:**
- All commits end with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Before any commit that touches `.py`, format changed files with the CI-pinned ruff: `uvx ruff@0.1.14 check --fix <files>` then `uvx ruff@0.1.14 format <files>` (local ruff is a different version and will fail CI Smoke).
- Run the CLI/app as modules; the `timeout` shell command is unavailable on this macOS — run focused pytest selections, not the whole suite.

---

### Task 1: Scaffold `app/readiness/` package — models + markdown stub

**Files:**
- Create: `app/readiness/__init__.py`
- Create: `app/readiness/models.py`
- Create: `app/readiness/markdown.py`
- Test: `tests/test_readiness_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readiness_models.py
from app.readiness.models import ReadinessReport, ReadinessSignal
from app.readiness.markdown import report_to_markdown


def test_report_defaults_and_shape():
    report = ReadinessReport(verdict="ready")
    assert report.verdict == "ready"
    assert report.signals == []
    assert report.questions == []


def test_signal_fields():
    sig = ReadinessSignal(kind="vagueness", message="The request is vague.")
    assert sig.kind == "vagueness"
    assert sig.message == "The request is vague."


def test_markdown_includes_verdict_and_questions():
    report = ReadinessReport(
        verdict="clarify",
        signals=[ReadinessSignal(kind="vagueness", message="The request is vague.")],
        questions=["What platform?"],
    )
    md = report_to_markdown(report)
    assert "clarify" in md.lower()
    assert "What platform?" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.readiness'`

- [ ] **Step 3: Create the package init**

```python
# app/readiness/__init__.py
```
(empty file — package marker)

- [ ] **Step 4: Create the models**

```python
# app/readiness/models.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReadinessVerdict = Literal["ready", "clarify", "risky", "noise"]
SignalKind = Literal["unverifiable_reference", "vagueness", "risk", "noise"]


class ReadinessSignal(BaseModel):
    kind: SignalKind
    message: str


class ReadinessReport(BaseModel):
    verdict: ReadinessVerdict
    signals: list[ReadinessSignal] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Create the markdown stub**

```python
# app/readiness/markdown.py
from __future__ import annotations

from app.readiness.models import ReadinessReport

_VERDICT_TITLE = {
    "ready": "Ready to compile",
    "clarify": "Clarify before compiling",
    "risky": "Risky — review first",
    "noise": "Not a real task",
}


def report_to_markdown(report: ReadinessReport) -> str:
    lines = [f"## Readiness: {report.verdict} — {_VERDICT_TITLE[report.verdict]}", ""]
    if report.signals:
        lines.append("### Signals")
        for sig in report.signals:
            lines.append(f"- **{sig.kind}**: {sig.message}")
        lines.append("")
    if report.questions:
        lines.append("### Clarify first")
        for q in report.questions:
            lines.append(f"- {q}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_models.py -q`
Expected: PASS (3 passed)

- [ ] **Step 7: Format and commit**

```bash
uvx ruff@0.1.14 check --fix app/readiness/ tests/test_readiness_models.py
uvx ruff@0.1.14 format app/readiness/ tests/test_readiness_models.py
git add app/readiness/__init__.py app/readiness/models.py app/readiness/markdown.py tests/test_readiness_models.py
git commit -m "feat(readiness): add ReadinessReport model and markdown stub"
```

---

### Task 2: Unverifiable-reference detector (`reference_rules.py`)

This is the headline feature — it turns the AcmeCloud finding into a signal. It flags `<Name> SDK/API/...` constructs and CamelCase product tokens that are not well-known technologies.

**Files:**
- Create: `app/readiness/reference_rules.py`
- Test: `tests/test_readiness_reference_rules.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readiness_reference_rules.py
from app.readiness.reference_rules import detect_unverifiable_references


def test_flags_unknown_sdk():
    refs = detect_unverifiable_references("use the AcmeCloud SDK to deploy my model")
    assert refs == ["AcmeCloud SDK"]


def test_flags_camelcase_product_token():
    refs = detect_unverifiable_references("connect to FooBarHub and sync")
    assert "FooBarHub" in refs


def test_known_tech_not_flagged():
    refs = detect_unverifiable_references(
        "build a FastAPI endpoint that stores rows in Postgres"
    )
    assert refs == []


def test_plain_text_no_false_positive():
    assert detect_unverifiable_references("make my app faster") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_reference_rules.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.readiness.reference_rules'`

- [ ] **Step 3: Write the implementation**

```python
# app/readiness/reference_rules.py
from __future__ import annotations

import re

# Well-known technologies that must NOT be flagged as unverifiable.
KNOWN_TECH = frozenset(
    {
        "aws", "gcp", "azure", "openai", "anthropic", "openrouter", "github",
        "gitlab", "docker", "kubernetes", "k8s", "postgres", "postgresql",
        "mysql", "sqlite", "mongodb", "redis", "react", "nextjs", "fastapi",
        "django", "flask", "express", "node", "nodejs", "python", "typescript",
        "javascript", "stripe", "vercel", "netlify", "cloudflare", "huggingface",
        "pytorch", "tensorflow", "langchain", "llamaindex", "supabase", "firebase",
    }
)

# "AcmeCloud SDK", "FooBar API", "Baz CLI" — a name followed by a product suffix.
_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+)\s+(SDK|API|CLI|Cloud|Platform|Service)\b"
)
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
        if any(tok in f for f in found):
            continue
        found.append(tok)
    return found[:5]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_reference_rules.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Format and commit**

```bash
uvx ruff@0.1.14 check --fix app/readiness/reference_rules.py tests/test_readiness_reference_rules.py
uvx ruff@0.1.14 format app/readiness/reference_rules.py tests/test_readiness_reference_rules.py
git add app/readiness/reference_rules.py tests/test_readiness_reference_rules.py
git commit -m "feat(readiness): detect unverifiable technology references"
```

---

### Task 3: Language guard predicate (`language_guard.py`)

A pure predicate: is the output in a different language than a non-English input? English is the default and is never overridden.

**Files:**
- Create: `app/readiness/language_guard.py`
- Test: `tests/test_readiness_language_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readiness_language_guard.py
from app.readiness.language_guard import output_language_mismatch


def test_turkish_input_english_output_is_mismatch():
    assert output_language_mismatch(
        "Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?",
        "You are a performance engineer. Identify bottlenecks and suggest fixes.",
    )


def test_turkish_input_turkish_output_is_ok():
    assert not output_language_mismatch(
        "Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?",
        "Sen bir performans mühendisisin. Darboğazları bul ve çözüm öner.",
    )


def test_english_input_never_overridden():
    assert not output_language_mismatch("make my app faster", "Sen bir mühendissin.")


def test_empty_is_not_mismatch():
    assert not output_language_mismatch("", "anything")
    assert not output_language_mismatch("merhaba dünya", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_language_guard.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.readiness.language_guard'`

- [ ] **Step 3: Write the implementation**

```python
# app/readiness/language_guard.py
from __future__ import annotations

from app.heuristics import detect_language


def output_language_mismatch(input_text: str, output_text: str) -> bool:
    """True when a non-English input produced an output in a different language.

    English is the project's default language and is never overridden, so an
    English input always returns False.
    """
    if not input_text or not output_text:
        return False
    in_lang = detect_language(input_text)
    if in_lang == "en":
        return False
    return detect_language(output_text) != in_lang
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_language_guard.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Format and commit**

```bash
uvx ruff@0.1.14 check --fix app/readiness/language_guard.py tests/test_readiness_language_guard.py
uvx ruff@0.1.14 format app/readiness/language_guard.py tests/test_readiness_language_guard.py
git add app/readiness/language_guard.py tests/test_readiness_language_guard.py
git commit -m "feat(readiness): add output language-mismatch predicate"
```

---

### Task 4: Readiness analyzer (`analyzer.py`) — the regression net

Combines noise detection, risk, unverifiable references, and vagueness into a single verdict. Verdict precedence: `noise` → `risky` → `clarify` → `ready`. The tests assert the review's exact failing inputs now produce the right verdict.

**Files:**
- Create: `app/readiness/analyzer.py`
- Test: `tests/test_readiness_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readiness_analyzer.py
from app.readiness.analyzer import analyze_readiness


def test_acmecloud_is_clarify_with_unverifiable_signal():
    report = analyze_readiness("use the AcmeCloud SDK to deploy my model")
    assert report.verdict == "clarify"
    assert any(s.kind == "unverifiable_reference" for s in report.signals)


def test_vague_request_is_clarify_with_questions():
    report = analyze_readiness("make my app faster")
    assert report.verdict == "clarify"
    assert any(s.kind == "vagueness" for s in report.signals)


def test_gibberish_is_noise():
    assert analyze_readiness("asdf1234!!!!****").verdict == "noise"


def test_empty_is_noise():
    assert analyze_readiness("   ").verdict == "noise"


def test_greeting_is_noise():
    assert analyze_readiness("merhaba").verdict == "noise"


def test_concrete_request_is_ready():
    report = analyze_readiness(
        "build a FastAPI endpoint that accepts a CSV upload, validates rows, "
        "stores them in Postgres, and returns a job id"
    )
    assert report.verdict == "ready"


def test_sensitive_security_request_is_risky():
    report = analyze_readiness("add password hashing and session authentication")
    assert report.verdict == "risky"
    assert any(s.kind == "risk" for s in report.signals)


def test_turkish_request_is_not_noise():
    report = analyze_readiness("Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?")
    assert report.verdict != "noise"


def test_questions_capped_at_three():
    report = analyze_readiness("make it better, faster, nicer, cleaner, and improve it")
    assert len(report.questions) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_analyzer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.readiness.analyzer'`

- [ ] **Step 3: Write the implementation**

```python
# app/readiness/analyzer.py
from __future__ import annotations

import re

from app.heuristics import (
    detect_ambiguous_terms,
    detect_risk_flags,
    generate_clarify_questions,
)
from app.readiness.models import ReadinessReport, ReadinessSignal
from app.readiness.reference_rules import detect_unverifiable_references

GREETINGS = frozenset({"hi", "hello", "hey", "yo", "merhaba", "selam", "hola"})
# RISK_KEYWORDS categories that are genuinely sensitive. "infrastructure"
# (deploy/hosting) is intentionally excluded — it is context, not a blocker.
SENSITIVE_RISK = frozenset({"security", "privacy", "financial", "health", "legal"})
# Words that signal a vague ask even when no ambiguous term matches.
VAGUE_WORDS = frozenset(
    {"faster", "fast", "better", "good", "nicer", "nice", "cleaner", "improve", "optimize"}
)

_WORD_RE = re.compile(r"[A-Za-zğüşöçıİĞÜŞÖÇ]+")
_VOWEL_RE = re.compile(r"[aeıioöuüAEIİOÖUÜ]")
_SYMBOL_RUN_RE = re.compile(r"[^\w\s]{3,}")


def _is_noise(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    words = _WORD_RE.findall(stripped)
    if not words:
        return True
    if len(stripped) <= 20 and all(w.lower() in GREETINGS for w in words):
        return True
    if _SYMBOL_RUN_RE.search(stripped) and len(words) <= 2:
        return True
    if not any(_VOWEL_RE.search(w) for w in words):
        return True
    return False


def analyze_readiness(text: str, ir: object | None = None) -> ReadinessReport:
    if _is_noise(text):
        return ReadinessReport(
            verdict="noise",
            signals=[
                ReadinessSignal(
                    kind="noise",
                    message="This doesn't look like a real task — add a concrete request.",
                )
            ],
        )

    signals: list[ReadinessSignal] = []
    questions: list[str] = []

    risk_flags = [f for f in detect_risk_flags(text) if f in SENSITIVE_RISK]
    for flag in risk_flags:
        signals.append(
            ReadinessSignal(kind="risk", message=f"Touches a sensitive area: {flag}.")
        )

    references = detect_unverifiable_references(text)
    for ref in references:
        signals.append(
            ReadinessSignal(
                kind="unverifiable_reference",
                message=f"'{ref}' couldn't be verified — confirm it exists.",
            )
        )
        questions.append(f"Is '{ref}' a real, documented tool? Link its docs if so.")

    ambiguous = detect_ambiguous_terms(text)
    lower_words = set(text.lower().split())
    is_vague = bool(ambiguous) or bool(lower_words & VAGUE_WORDS)
    if is_vague:
        signals.append(
            ReadinessSignal(kind="vagueness", message="The request is vague — specifics are missing.")
        )
        for question in generate_clarify_questions(ambiguous):
            if question not in questions:
                questions.append(question)

    questions = questions[:3]

    if risk_flags:
        verdict = "risky"
    elif references or is_vague:
        verdict = "clarify"
    else:
        verdict = "ready"

    return ReadinessReport(verdict=verdict, signals=signals, questions=questions)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_analyzer.py -q`
Expected: PASS (9 passed)

If `test_concrete_request_is_ready` or `test_sensitive_security_request_is_risky` fails, print the actual flags to confirm the heuristic categories: `python -c "from app.heuristics import detect_risk_flags; print(detect_risk_flags('add password hashing and session authentication'))"` — it should contain `security`. Adjust only the test's input wording if the real category differs; do not weaken `SENSITIVE_RISK`.

- [ ] **Step 5: Format and commit**

```bash
uvx ruff@0.1.14 check --fix app/readiness/analyzer.py tests/test_readiness_analyzer.py
uvx ruff@0.1.14 format app/readiness/analyzer.py tests/test_readiness_analyzer.py
git add app/readiness/analyzer.py tests/test_readiness_analyzer.py
git commit -m "feat(readiness): add analyze_readiness verdict engine"
```

---

### Task 5: Wire readiness + language guard into `/compile`

Add the `readiness` field to `CompileResponse`, compute it, and apply the deterministic language guard that replaces a language-mismatched LLM render with the language-correct `emit_*_v2` output.

**Files:**
- Modify: `api/routes/compile.py` (CompileResponse at line 89; endpoint body around lines 357-504)
- Test: `tests/test_readiness_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readiness_api.py
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _compile(text: str) -> dict:
    resp = client.post(
        "/compile",
        json={"text": text, "v2": False, "render_v2_prompts": True},
    )
    assert resp.status_code == 200
    return resp.json()


def test_response_includes_readiness_verdict():
    body = _compile("use the AcmeCloud SDK to deploy my model")
    assert body["readiness"]["verdict"] == "clarify"
    kinds = {s["kind"] for s in body["readiness"]["signals"]}
    assert "unverifiable_reference" in kinds


def test_turkish_input_keeps_turkish_v2_output():
    body = _compile("Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?")
    from app.heuristics import detect_language

    assert detect_language(body["system_prompt_v2"]) == "tr"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readiness_api.py -q`
Expected: FAIL — `KeyError: 'readiness'` (field not present yet).

- [ ] **Step 3: Add the `readiness` field to `CompileResponse`**

In `api/routes/compile.py`, in `class CompileResponse` (line 89), add the field after `critique`:

```python
    critique: dict | None = None
    readiness: dict | None = None
```

- [ ] **Step 4: Add imports at the top of `api/routes/compile.py`**

Add near the other `app.` imports:

```python
from app.readiness.analyzer import analyze_readiness
from app.readiness.language_guard import output_language_mismatch
```

- [ ] **Step 5: Apply the language guard after the v2 render**

In `compile_endpoint`, immediately after the `if req.render_v2_prompts and ir2 is not None:` block (the one ending at line ~418 that fills `sys_v2/user_v2/plan_v2/exp_v2`), insert:

```python
    if ir2 is not None and output_language_mismatch(
        req.text, " ".join(filter(None, [sys_v2, user_v2, exp_v2]))
    ):
        sys_v2 = emit_system_prompt_v2(ir2)
        user_v2 = emit_user_prompt_v2(ir2)
        plan_v2 = emit_plan_v2(ir2)
        exp_v2 = emit_expanded_prompt_v2(ir2, diagnostics=req.diagnostics)
```

(`emit_system_prompt_v2`, `emit_user_prompt_v2`, `emit_plan_v2`, `emit_expanded_prompt_v2` are already imported in this module — confirm with `grep -n "emit_system_prompt_v2" api/routes/compile.py`.)

- [ ] **Step 6: Compute readiness and attach it to both return paths**

Just before `elapsed = int((time.time() - t0) * 1000)` (line ~454), add:

```python
    readiness = analyze_readiness(req.text, ir2).model_dump()
```

Then add `readiness=readiness,` to BOTH `CompileResponse(...)` returns — the safety-refusal return (line ~471) and the normal return (line ~483).

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_readiness_api.py -q`
Expected: PASS (2 passed)

If `test_turkish_input_keeps_turkish_v2_output` fails, confirm the deterministic emitter honors language: `python -c "from app.emitters import emit_system_prompt_v2; from app.compiler import compile_text_v2; print(emit_system_prompt_v2(compile_text_v2('Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?', offline_only=True))[:60])"` — output should be Turkish.

- [ ] **Step 8: Run the existing compile tests to confirm no regression**

Run: `python -m pytest tests/test_compile_policy_api.py tests/test_readiness_api.py -q`
Expected: PASS (all)

- [ ] **Step 9: Format and commit**

```bash
uvx ruff@0.1.14 check --fix api/routes/compile.py tests/test_readiness_api.py
uvx ruff@0.1.14 format api/routes/compile.py tests/test_readiness_api.py
git add api/routes/compile.py tests/test_readiness_api.py
git commit -m "feat(compile): attach readiness report and enforce output language"
```

---

### Task 6: Web — readiness banner, types, and truthful mode label

Render the readiness verdict above the output tabs and replace the unenforced "No hallucinations" label.

**Files:**
- Modify: `web/lib/api/types.ts` (CompileResponse type, lines ~74-90)
- Create: `web/app/components/ReadinessBanner.tsx`
- Create: `web/app/components/ReadinessBanner.test.tsx`
- Modify: `web/app/page.tsx` (banner placement before the tabs block; label at the conservative-mode toggle)

- [ ] **Step 1: Add the readiness types to `web/lib/api/types.ts`**

Above `export type CompileResponse`, add:

```typescript
export type ReadinessVerdict = "ready" | "clarify" | "risky" | "noise";

export type ReadinessSignal = {
  kind: "unverifiable_reference" | "vagueness" | "risk" | "noise";
  message: string;
};

export type ReadinessReport = {
  verdict: ReadinessVerdict;
  signals: ReadinessSignal[];
  questions: string[];
};
```

Then add this field inside `CompileResponse` (after `critique?: Critique | null;`):

```typescript
  readiness?: ReadinessReport | null;
```

- [ ] **Step 2: Write the failing component test**

```tsx
// web/app/components/ReadinessBanner.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReadinessBanner from "./ReadinessBanner";

describe("ReadinessBanner", () => {
  it("renders nothing when there is no report", () => {
    const { container } = render(<ReadinessBanner report={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the verdict title and a clarification question", () => {
    render(
      <ReadinessBanner
        report={{
          verdict: "clarify",
          signals: [{ kind: "unverifiable_reference", message: "'AcmeCloud SDK' couldn't be verified." }],
          questions: ["Is 'AcmeCloud SDK' a real, documented tool?"],
        }}
      />,
    );
    expect(screen.getByText(/clarify before compiling/i)).toBeInTheDocument();
    expect(screen.getByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.getByText(/real, documented tool/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web && npx vitest run app/components/ReadinessBanner.test.tsx`
Expected: FAIL — cannot resolve `./ReadinessBanner`.

- [ ] **Step 4: Create the component**

```tsx
// web/app/components/ReadinessBanner.tsx
import type { ReadinessReport, ReadinessVerdict } from "../../lib/api/types";

const VERDICT_META: Record<ReadinessVerdict, { title: string; tone: string }> = {
  ready: { title: "Ready to compile", tone: "text-green-300 border-green-500/40 bg-green-500/10" },
  clarify: { title: "Clarify before compiling", tone: "text-amber-300 border-amber-500/40 bg-amber-500/10" },
  risky: { title: "Risky — review first", tone: "text-red-300 border-red-500/40 bg-red-500/10" },
  noise: { title: "Not a real task", tone: "text-zinc-300 border-zinc-500/40 bg-zinc-500/10" },
};

export default function ReadinessBanner({ report }: { report?: ReadinessReport | null }) {
  if (!report) return null;
  const meta = VERDICT_META[report.verdict];
  return (
    <div className={`rounded-xl border px-4 py-3 mb-3 ${meta.tone}`} role="status" aria-live="polite">
      <div className="text-sm font-bold">{meta.title}</div>
      {report.signals.length > 0 && (
        <ul className="mt-2 space-y-1">
          {report.signals.map((s, i) => (
            <li key={i} className="text-xs text-zinc-200">{s.message}</li>
          ))}
        </ul>
      )}
      {report.questions.length > 0 && (
        <div className="mt-2">
          <div className="text-[11px] uppercase tracking-wide opacity-70">Clarify first</div>
          <ul className="mt-1 space-y-1">
            {report.questions.map((q, i) => (
              <li key={i} className="text-xs text-zinc-100">· {q}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd web && npx vitest run app/components/ReadinessBanner.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 6: Render the banner in `web/app/page.tsx`**

Add the import near the other component imports (e.g. after the `QualityCoach` import):

```tsx
import ReadinessBanner from "./components/ReadinessBanner";
```

Then, immediately before the element marked `{/* Tabs + policy verdict */}` (around line 343), render the banner:

```tsx
                {result?.readiness && <ReadinessBanner report={result.readiness} />}
```

(Use the same accessor the file already uses for the compile result — confirm the result variable name with `grep -n "result?.system_prompt_v2\|const result\|result =" web/app/page.tsx`.)

- [ ] **Step 7: Replace the unenforced "No hallucinations" label**

Run `grep -n "No hallucinations" web/app/page.tsx` (appears in the conservative-mode toggle aria-label, title, and visible label). Replace every occurrence of the string `No hallucinations` with `Conservative mode`. The product no longer claims something it does not enforce; truthfulness now lives in the readiness verdict.

- [ ] **Step 8: Run the web checks**

Run: `cd web && npx vitest run app/components/ReadinessBanner.test.tsx && npm run build`
Expected: tests PASS and the production build succeeds.

- [ ] **Step 9: Commit**

```bash
git add web/lib/api/types.ts web/app/components/ReadinessBanner.tsx web/app/components/ReadinessBanner.test.tsx web/app/page.tsx
git commit -m "feat(web): show readiness banner and drop unenforced no-hallucinations label"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** verdict model (Task 4), deterministic signals incl. unverifiable references (Tasks 2, 4), clarification questions (Task 4), risky=sensitive-only with infrastructure excluded (Task 4), language guard (Tasks 3, 5), drop "No hallucinations" (Task 6), `app/readiness/` mirrors `app/pr_safety/` (Tasks 1-4), `readiness` on `CompileResponse` (Task 5), web banner (Task 6), regression tests on the review's exact inputs (Task 4).
- **No second LLM** anywhere — every check is regex/heuristic. The optional LLM "second opinion" is explicitly out of scope.
- **Determinism:** the language guard never translates; it swaps in the language-correct deterministic `emit_*_v2` render, which `app/emitters.py` already produces from `ir.language`.
- **Out of scope (later slices):** executable `.md`/`.json` export and agent packs (Slice 2); README/positioning/star story (Slice 3).
