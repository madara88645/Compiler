# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2025-08-25
### Changed
- IR v2 is now the default in API (`v2: true` by default) and CLI (use `--v1` to access legacy output and prompt renderers)
- IR v2 metadata now includes `ir_version=2.0` and `package_version=2.0.0`
### Added
- API continues to return IR v1 alongside IR v2 when requested; default response includes `ir_v2`
### Migration Notes
- If you rely on prompt renderers (system/user/plan/expanded), use `--v1` in CLI or `{"v2": false}` in API until v2 renderers are introduced

## [2.0.1] - 2025-08-27
### Added
- Desktop UI: Trace toggle and new Trace tab
- Desktop UI: IR v2 JSON tab
- Desktop UI: Save dialog to export combined Markdown or IR JSON (v1/v2)
### Changed
- Desktop UI: Status line now shows processing time and heuristic versions

## [2.0.2] - 2025-08-28
### Added
- Desktop UI: Intent chips under the summary (from IR v2 `intents`)
- Desktop UI: IR v2 Constraints Viewer tab (table with priority/origin/id/text) and Copy action

## [2.0.3] - 2025-08-30
### Added
- Desktop UI: "Send to OpenAI" controls (model field, Use Expanded toggle, send button) and an "OpenAI Response" tab
### Docs
- README updated to include UI OpenAI send instructions and screenshot placeholder (`docs/images/desktop_openai.png`)

## [2.0.4] - 2025-09-02
### Added
- Persona: New `developer` coding assistant persona with precedence over teacher when coding context is detected
- Heuristics: Live debug detection (MRE, stack trace analysis, iterative fixes) and coding constraints (runnable examples, tests/usage)
- IR v2: `persona` now permits `developer`; new `intents` value `debug` when live debug is detected
- UI: IR v2 Constraints Viewer gains an "Only live_debug" filter checkbox
### Tests
- New tests covering developer persona triggers and IR v2 debug intent
### Docs
- README updated with developer/live debug notes, CLI examples, and UI filter mention

## [0.1.9] - 2025-08-24
### Added
- External patterns config loader (YAML/JSON) for domain, ambiguity, risk keywords override
- Structured clarification objects (`metadata.clarify_questions_struct` with category + question)
- Temporal signal extraction (`metadata.temporal_flags`) for years, quarters, relative time phrases
- Quantity extraction (`metadata.quantities`) for numeric + unit patterns (minutes, hours, days, counts, ranges)
- Constraint origin tracking (`metadata.constraint_origins`) mapping each constraint to its heuristic source
- Teaching mode constraints refactored to integrate pre-IR creation (fixing regression)
- IR v2 (preview, behind flag): new `IRv2` model with typed `constraints {id,text,origin,priority}` and `intents` + typed `steps`; Python API `compile_text_v2`, HTTP API `v2: true` returns `ir_v2`
- IR v2 JSON Schema: `schema/ir_v2.schema.json`
- Basic Spanish (es) language support across detection, models/schemas, and emitters (localized labels)
### Changed
- Rebuilt `compile_text` for clearer pipeline order and early teaching enrichment
- Domain confidence now `None` (instead of 0.0) when domain is `general` or no evidence
- Heuristic version bumped to 2025.08.21-1
 - Heuristic2 (v2) version introduced: 2025.08.23-0 (for IR v2 mapping/priorities)
### Fixed
- Restored teaching intent constraints (friendly tone, pedagogical flow, source recommendations)
- Regression causing missing duration/level constraints in teaching tests

## [0.1.5] - 2025-08-18
### Added
## [0.1.6] - 2025-08-19
### Added
### Changed
### Fixed

### Changed
### Fixed

## [0.1.7] - 2025-08-19
### Added
- PII detection (email, phone, credit card, IBAN) -> metadata.pii_flags and privacy constraints
- Domain candidates list (metadata.domain_candidates) for broader coverage insight
- Trace now includes pii_flags and domain_candidates
### Changed
- Heuristic version bumped to 2025.08.19-2 for coverage/accuracy iteration
### Fixed
- None (backward compatible; existing tests unaffected)
## [0.1.8] - 2025-08-20
### Added
- Domain confidence ratio (metadata.domain_confidence) + raw counts (metadata.domain_scores) + scoring mode (metadata.domain_score_mode)
- Trace lines now show domain_conf and domain_scores
### Changed
- Heuristic version bumped to 2025.08.20-1 for confidence feature
### Fixed
- None (all tests pass)

- Offline Desktop UI (`ui_desktop.py`) with prompt input, diagnostics toggle, copy buttons, summary header
### Changed
- README updated (Desktop UI feature + usage section, screenshots placeholders)

## [0.1.4] - 2025-08-16
### Added
- Always-on Clarification Questions block (appears before diagnostics when ambiguous terms exist)
- Lightweight Assumptions block (missing details, disclaimer for risk domains, variant differentiation rule)
### Changed
- README updated (features list + new Assumptions & Clarification Blocks section)

## [0.1.2] - 2025-08-15
### Added
- Extended heuristics: risk flags (financial/health/legal), entity extraction, complexity estimate, ambiguous term detection + clarify questions, code request detection
- New metadata fields: risk_flags, entities, complexity, ambiguous_terms, clarify_questions, code_request
### Changed
- Constraints automatically enriched for risk domains, ambiguous terms, and code examples with inline comments

## [0.1.1] - 2025-08-14
### Added
- Structured persona field (schema + model) with heuristic selection and evidence metadata
- Persona surfaced in System Prompt, Expanded Prompt context, and CLI output
### Changed
- README updated (persona in features, schema, API response example)

## [0.1.1] - 2025-08-14
### Added
- Language-specific teaching personas (TR / EN)
- Analogy usage constraints for teaching mode (TR & EN)
- Explicit role display in CLI output
### Changed
- Teaching mode feature list updated in README (persona + analogies)

## [0.1.0] - 2025-08-12
- Initial release: Prompt Compiler App with IR, API, CLI, tests
- Recency rule, language/domain detection
- Expanded Prompt and teaching mode with level/duration
- Inputs extraction (interest, budget, format)
