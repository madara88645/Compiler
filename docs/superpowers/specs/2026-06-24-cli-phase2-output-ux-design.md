# CLI Phase 2 — compile/pack Output & UX

**Date:** 2026-06-24
**Scope:** `compile` and `pack` output only. New `cli/render.py`; edits to `cli/commands/core.py`, `app/utils.py`, and a one-line fix in `app/agents/context_strategist.py`.
**Status:** Approved design → ready for implementation plan.
**Predecessor:** Phase 1 (declutter + `--version` + install fix) merged as #844.

## Özet (TR)
Flagship `compile`'ın varsayılan çıktısı şu an insan için bozuk: `--render-v2` False varsayılan
ve prompt bölümleri ona bağlı olduğu için kullanıcı sadece 200+ satır ham IR JSON görüyor,
kopyalanabilir prompt yok. Faz 2: varsayılanı **insan-öncelikli** yapar (özet kart +
System/User/Plan/Expanded), ham IR'ı `--json-only`'ye taşır, `pack` çıktısına başlık ekler,
ölü `--quiet` flag'ini düzeltir ve her offline run'da stderr'e basılan `[STRATEGIST]` gürültü
satırını `logger.debug`'a indirir. Tüm rich render tek bir `cli/render.py`'de toplanır;
makine yolları (`--json-only`/`--out`/`--format`/`--quiet`) düz kalır.

## Context / Problem (verified against source)
`promptc compile "..."` today prints **only raw IR JSON** and no usable prompt. Confirmed:
`render_v2` defaults to `False` (`cli/commands/core.py:396`), and the prompt sections are gated
on `if ir or (ir2 and render_v2)` (`core.py:311`). With the default v2 path (`v1=False`,
`render_v2=False`) that condition is always false, so only `print(rendered)` (raw orjson IR,
`core.py:310`) runs. Observed directly in the Phase 1 install smoke test.

Other verified issues:
- **`[STRATEGIST]` noise:** `app/agents/context_strategist.py:101` is an unconditional
  `print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)` — it fires on every
  no-credential/offline run and reads like an error. (It goes to **stderr**, not stdout; the
  survey's "corrupts pack JSON" claim was an overstatement, but the noisy stderr line on normal
  runs is still wrong — everywhere else this is `logger.debug`.)
- **Rendering inconsistency:** `compile` uses bare rich `print` with inline markup; `fix`/`compare`
  use `Console`+`Panel`+`Table`; `pack` uses plain `typer.echo`. A `Console()` is defined at
  `core.py:52` but the central command doesn't use it.
- **Latent markup bug:** emitter strings contain tokens like `[clarify]`, `[policy]`, `[task]`
  that rich's markup parser silently swallows on the `print(...[bold]...)` path.
- **Dead `--quiet`:** documented as "print only system prompt" but emits a blank line on the
  default v2 path.
- **`pack` polish:** `_render_prompt_pack_md/_render_prompt_pack_txt` (in `app/utils.py`) are used
  **only** by the pack command (`core.py:963/966`) — no API usage — so changing them is CLI-scoped
  and safe. The `.txt` form currently bleeds markdown (`### Context`).

## Goals
- `promptc compile "..."` (no flags) shows a concise summary card + rendered System / User / Plan /
  Expanded prompts — usable, copy-pasteable output.
- Raw IR JSON is available via `--json-only` (unchanged, parseable contract).
- One consistent rich "house style" for human output, centralized in `cli/render.py`.
- `--quiet` prints the real v2 system prompt; `pack` output gets a compact metadata header and a
  clean plain-text `.txt`.
- Normal offline runs no longer print an error-looking `[STRATEGIST]` line.

## Non-Goals (explicit)
- **No changes to `app/emitters.py` content** or the heuristics/compiler. Emitters return
  display-agnostic strings by design; rendering only reformats them.
- **Upstream IR/heuristic bugs are out of scope** (constraint "garbage" text, `under 200 words`→
  `budget:200` misparse, Goals==Tasks duplication). These live in the shared v2 layer and need a
  separate, larger PR with broader test coverage.
- **Secondary commands deferred:** `validate` / `compare` / `diff` polish (schema dump, Turkish
  leak, exit codes) is a later phase.
- No new output flags beyond what exists (`--json-only`, `--quiet`, `--out`, `--format`, `--diagnostics`).
- Machine-output paths stay plain — never routed through rich.

## Design

### A) `cli/render.py` (new — CLI presentation layer)
Single home for human-tier rendering. Pure presentation; takes already-computed strings/dicts.
- `get_console() -> Console` — shared Console factory.
- `render_summary_card(console, ir2: dict) -> None` — a rich `Panel`/`Table` showing
  Persona, Domain, Risk (`policy.risk_level`/`metadata`), #Goals, #Constraints, output format.
- `render_prompt_sections(console, system, user, plan, expanded) -> None` — one `console.rule()` +
  body per section, rendered with `markup=False` / `rich.markup.escape` so `[clarify]` etc. are not
  swallowed. Fixes the latent markup bug.
- Section-title constants (System Prompt / User Prompt / Plan / Expanded) shared so headers aren't
  duplicated across the console view and pack.
Hard rule baked into the module's docstring: machine-output paths must NOT use these helpers.

### B) `compile` (`cli/commands/core.py`)
- **Default (no output flags):** compute the v2 emitter strings regardless of `render_v2`, then
  `render_summary_card(...)` + `render_prompt_sections(...)`. Remove the default `print(rendered)`
  raw-IR dump.
- `--json-only`: unchanged — plain raw IR JSON to stdout (parseable).
- `--quiet`: emit the real v2 system prompt (plain stdout). Fixes the dead flag.
- `--out` / `--format` / `--from-file` write paths: unchanged (plain).
- `--render-v2`: now redundant (default renders); keep as an accepted no-op for back-compat.
- `--diagnostics`: keep current meaning (risk & ambiguity in expanded). If it remains a no-op on
  the v2 path, make it append the diagnostics block to the rendered Expanded section.

### C) `pack` (`app/utils.py` + `cli/commands/core.py`)
- In `_render_prompt_pack_md` and `_render_prompt_pack_txt`: prepend a compact header
  (Domain / Risk / Persona / IR version).
- In `_render_prompt_pack_txt`: replace markdown bleed (`### Context`) with plain `--- Context ---`
  and emoji constraint labels with plain text (e.g. `Restriction:` / `Flow:`).
- These return plain strings (the copy/paste/file artifact); they do NOT use rich.

### D) `[STRATEGIST]` noise fix (`app/agents/context_strategist.py:101`)
Replace `print(f"[STRATEGIST] Query expansion failed: {e}", file=sys.stderr)` with a
`logger.debug(...)` call (add/Reuse a module logger, matching `app/llm_engine/client.py`). Standalone
and independently valuable — ships as its own small PR first.

## Files Affected
- `cli/render.py` — new presentation module.
- `cli/commands/core.py` — compile default/quiet rendering wiring; pack header pass-through.
- `app/utils.py` — pack header + plain-text `.txt` cleanup (CLI-only functions).
- `app/agents/context_strategist.py` — one-line `print`→`logger.debug`.
- `tests/test_cli_phase2.py` (new) + updates to existing tests that assert default-compile-is-JSON.

## Testing & Verification
- `cli/render.py` unit tests: summary card contains the expected fields; `render_prompt_sections`
  output preserves `[clarify]`-style tokens (markup not swallowed).
- `compile` default (CliRunner): stdout contains "System Prompt"/"User Prompt"/"Plan"/"Expanded"
  and summary fields; stdout does NOT contain a raw IR dump (`"version": "2.0"`).
- `--json-only`: stdout parses as JSON (contract preserved).
- `--quiet`: stdout non-empty (the system prompt).
- `pack`: output contains the new header; `.txt` contains no `### ` markdown headers.
- Update any existing golden/compile test that asserted the old default JSON output.
- Full pytest suite green; ruff clean; CI green.

## Risks
- **Medium.** The flagship default output changes (behavior change), so existing tests/scripts that
  relied on default-is-JSON must switch to `--json-only`; golden tests get updated. Also touches
  `app/utils.py` (pack, CLI-only) and a one-line `app/agents` fix. Mitigated by: machine paths stay
  plain, emitters untouched, focused scope, and the change is reversible. `prcompiler` is a new PyPI
  name with no install base, so the default flip is least disruptive now.

## Rollout (small & reversible)
- **PR-A:** `[STRATEGIST]` noise fix (Section D) — standalone, tiny, ships first.
- **PR-B:** `cli/render.py` + compile human-first default + pack header + `--quiet` fix (Sections A–C).
- Both draft until CI green + clean-venv check that `promptc compile "..."` shows rendered prompts.
