# Compile Readiness Layer — Slice 1 (design)

Date: 2026-06-27
Status: Approved (design)

## Goal

Add a deterministic, no-LLM "request readiness" check that runs as part of
`/compile` and tells the user whether their request is safe to compile **before**
they spend a model call on it. This mirrors the PR Safety philosophy
(`app/pr_safety/`) — fixed rules first, optional AI refine later, validation
always — but applied to the compile *input* instead of a PR.

The headline outcome: turn the review's sharpest criticism (the product invented
a fake `AcmeCloud SDK` while claiming "no hallucinations") into the product's
signature feature — "Compiler catches what's wrong with your request."

Primary surface for this slice: the web compile screen (`web/app/page.tsx`). CLI
and Markdown/JSON export are later slices.

## Background — why (verified against the code)

An external agent review judged the public web compile flow (`v2: true`,
conservative mode, see `web/app/hooks/useCompiler.ts`). Findings, classified
against the codebase:

- **Hallucination (AcmeCloud)** — the conservative prompt already forbids
  inventing APIs, but the only guard (`CriticAgent`) is advisory and cannot
  change the output. Real weakness: no deterministic, non-advisory check.
- **Turkish input → English output** — `detect_language` returns `tr` for that
  input, and both worker prompts state "Turkish → Turkish", yet the rendered
  output was English. Real enforcement gap (LLM non-compliance or v2 emitter not
  honoring language).
- **Gibberish `asdf1234` → "hello"** — the LLM pattern-matched the greeting
  examples (Examples 3/4 in `worker_conservative.md`). Real, low severity.
- **"No hallucinations" badge** — shown in conservative mode
  (`web/app/page.tsx`). An unenforced promise; this is what made the review call
  the product untrustworthy rather than merely weak.

The "generic output / no code" complaint is a positioning issue (conservative
mode is *designed* to stay generic) and is out of scope for this slice.

## Non-goals (explicit)

- **No second LLM / "LLM-as-judge".** The verdict is 100% deterministic in this
  slice. Adding AI to fix AI unreliability defeats the purpose and adds cost.
- **No executable export** (real `.md`/`.json` download, agent packs) — Slice 2.
- **No repositioning / README / star-story work** — Slice 3.
- **No changes to the compile generation behavior itself.** Readiness annotates;
  it does not rewrite the compiled prompt, and it never blocks output.
- The project's primary language is English. Readiness labels, code, and UI
  strings are English. Language matching only ensures the *generated output*
  follows the user's input language when that input is non-English.

## Verdict model

`ReadinessReport.verdict` is one of:

- `ready` — specific enough, no unverifiable references, no risky areas.
- `clarify` — vague, missing key info, or contains unverifiable references;
  carries 1–3 clarification questions.
- `risky` — touches genuinely sensitive domains (auth, secrets, db, PII).
- `noise` — gibberish, empty, or a bare greeting; not a real task.

Precedence (first match wins): `noise` → `risky` → `clarify` → `ready`.

Note: infrastructure verbs like "deploy" are *not* auto-`risky` on their own.
The AcmeCloud example below stays `clarify` (unverifiable reference + missing
info), not `risky`, because deploying a model is not a sensitive-data domain.

The verdict is **advisory in effect**: it is always surfaced, but compile output
is still returned below it. The existing SafetyHandler block (prompt
injection / secret exfiltration, see `api/routes/compile.py`) is unchanged and
remains the only thing that empties output.

## Deterministic signals

Reuse existing heuristics — do not reimplement:

- `detect_risk_flags(text) -> list[str]` — auth/db/secret/deploy → `risky`.
- `detect_ambiguous_terms(text) -> list[str]` + length/specificity → vagueness.
- `detect_pii(text)` — feeds `risky`.
- `detect_language(text) -> str` — drives the language guard (below).

New in this slice:

- **Unverifiable-reference detector** (`app/readiness/reference_rules.py`) — flags
  proper-noun technology references the request leans on but that cannot be
  verified: patterns like `<CapitalizedName> SDK|API|CLI|Cloud|Platform` and
  standalone CamelCase product-looking tokens, minus a small allowlist of
  well-known names. Output is a *warning*, never a rewrite: "'AcmeCloud SDK'
  couldn't be verified — confirm it exists." This is the AcmeCloud feature.
- **Clarification-question generator** — deterministic, derived from what is
  missing (no concrete inputs, no constraints, vague action verb). Max 3.
- **Noise detector** — share of non-word characters / token entropy / very short
  length / greeting-only → `noise`.

## Enforcement guards (bundled correctness fixes)

1. **Language match** — compare `detect_language(input)` with
   `detect_language(rendered_output)`. If the input is non-English (e.g. `tr`)
   and the output does not match, correct it so the output language follows the
   input. English is the default and fallback language. Implemented as a
   deterministic post-check on the compile response, independent of the LLM.
2. **Greeting/noise bleed** — when the input is `noise`, the readiness verdict
   says so plainly instead of letting the generator map it to "hello".
3. **Replace the "No hallucinations" badge** (`web/app/page.tsx`) with the
   truthful readiness verdict chip (Ready / Clarify / Risky / Noise). The product
   stops promising something it does not enforce.

## Module structure

New `app/readiness/`, mirroring `app/pr_safety/` for codebase consistency:

| pr_safety | readiness (new) | responsibility |
|---|---|---|
| `analyzer.py` | `analyzer.py` | `analyze_readiness(text, ir=None) -> ReadinessReport` |
| `models.py` | `models.py` | `ReadinessReport`, `ReadinessSignal` schemas |
| `path_rules.py` | `reference_rules.py` | unverifiable-reference detection |
| `markdown.py` | `markdown.py` | report → Markdown (stub now, used by Slice 2) |

`analyze_readiness` is pure, deterministic, offline, and independently testable —
no imports from the LLM engine.

## API contract

- `ReadinessReport` is added as an optional `readiness` field on
  `CompileResponse` (alongside the existing `critique` field).
- `api/routes/compile.py` calls `analyze_readiness(req.text, ir2)` after the IR
  is built and attaches the report. The language post-check runs here too, on the
  v2 output fields, before the response is returned.
- No new request fields; readiness always runs (it is cheap and deterministic).

## Web surface

- A readiness banner renders between the request box and the output tabs in
  `web/app/page.tsx`, styled by verdict (green/amber/red/gray). It shows the
  verdict, the flagged signals, and any clarification questions. It does not
  block or hide the compiled output.
- The conservative-mode "No hallucinations" badge is replaced by the verdict
  chip.
- New `ReadinessBanner` component; `CompileResponse` type in
  `web/lib/api/types.ts` gains the `readiness` shape.

## Testing

Deterministic unit tests asserting the verdict for the review's exact inputs —
this is the regression net proving the review's failures are now caught:

- `use the AcmeCloud SDK to deploy my model` → `clarify`, unverifiable-reference
  signal present.
- `make my app faster` → `clarify`, vagueness signal + questions.
- `asdf1234!!!!****` → `noise`.
- `Uygulamam çok yavaş, hızlandırmak için ne yapmalıyım?` → language guard keeps
  output in Turkish; verdict `clarify`.
- A clear concrete request (e.g. the FastAPI endpoint prompt) → `ready`.
- A request touching auth/db → `risky`.

Plus: `analyze_readiness` unit tests per signal, and a `reference_rules` test for
the allowlist boundary. No network, no LLM, no new dependencies.

## Out of scope / future slices

- Slice 2 — executable export: real `.md`/`.json` download for compile output,
  agent-pack export, wire up `app/readiness/markdown.py`.
- Slice 3 — positioning: default-mode decision, messaging, README before/after,
  the #780→#807 star story.
- Optional LLM "second opinion" that refines wording but can never override the
  deterministic verdict.
