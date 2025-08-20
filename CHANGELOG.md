# Changelog

All notable changes to this project will be documented in this file.

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
