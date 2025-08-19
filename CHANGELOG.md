# Changelog

All notable changes to this project will be documented in this file.

## [0.1.5] - 2025-08-18
### Added
## [0.1.6] - 2025-08-19
### Added
- Heuristic version tagging (metadata.heuristic_version)
- Deterministic IR signature hash (metadata.ir_signature)
- CLI flags: --json-only, --quiet, --persona override
- API fields: processing_ms, request_id, heuristic_version
- Expanded Prompt follow-up questions block
### Changed
- Constraint de-duplication / normalization pass
### Fixed
- None (backward compatible)

- Version exposure: `/version` API endpoint and `promptc version` CLI command
- Heuristic expansions: cloud domain (AWS/Azure/GCP), broader finance/health/legal risk terms, new ambiguous terms (secure, resilient), extra persona triggers (workshop, survey, accountability, growth), new summary keywords (abstract, condense, outline), variant keyword (choices), code request terms (script, algorithm), additional recency phrases (this week, this month)
### Changed
- README converted fully to English; feature list updated with Awareness Extensions
- Extended domain/persona/risk/ambiguity coverage reflected in documentation
### Fixed
- None (all existing tests still pass)


## [0.1.3] - 2025-08-15
### Added
- Offline Desktop UI (`ui_desktop.py`) with prompt input, diagnostics toggle, copy buttons, summary header
- Light/Dark theme toggle for desktop UI
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
