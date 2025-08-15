# Changelog

All notable changes to this project will be documented in this file.

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
