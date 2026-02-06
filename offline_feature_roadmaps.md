# Offline Heuristic Development Roadmaps

Use these prompts to guide other AI Agents in building a powerful, LLM-free Offline Compiler.

---

## Roadmap 1: The Structure Architect (Structural & Templating Engine)

**Goal:** Transform raw, unstructured user text into a pristine, standardized prompt format (Markdown/XML) using strictly deterministic regex rules.

**Prompt for Agent:**
```markdown
# MISSION: BUILD THE OFFLINE STRUCTURE ENGINE

You are an expert Python Backend Engineer specialized in Regex and Text Parsing.
Your task is to build a `StructureHandler` in `app/heuristics/handlers/structure.py` that formats raw prompts without using an LLM.

## OBJECTIVES
1. **Section Segmentation**:
   - Detect implied sections in raw text (e.g., "Act as...", "Context is...", "Do not...").
   - Force-split the output into standard Markdown headers: `### Role`, `### Context`, `### Task`, `### Constraints`.

2. **Variable Injection**:
   - Identify capitalized placeholders or potential variables (e.g., "USER_NAME", "the Date").
   - Convert them into standard `{{VARIABLE}}` syntax.
   - Output a "Variables" section at the top of the prompt.

3. **Output Formatting**:
   - Detect keywords like "JSON", "CSV", "XML", "Table".
   - Automatically inject a predefined `<output_format>` XML block at the end of the prompt with strict schema examples for the detected format.

4. **DeepSpec Integration**:
   - Ensure the final output adheres to the "DeepSpec" standard (concise, imperative, structured).

## DELIVERABLES
- `StructureHandler` class in `app/heuristics/handlers/structure.py`.
- Unit tests validating that messily formatted text is converted into clean Markdown structure.
- **CONSTRAINT**: NO LLM CALLS. Pure Python/Regex only.
```

---

## Roadmap 2: The Logic Engineer (Constraints & Reasoning)

**Goal:** Simulate "Chain of Thought" reasoning by identifying logical dependencies, inputs/outputs, and negative constraints through advanced pattern matching.

**Prompt for Agent:**
```markdown
# MISSION: BUILD THE OFFLINE LOGIC EXTRACTOR

You are a Senior NLP Engineer specialized in Rule-Based Systems and Computational Linguistics.
Your task is to significantly upgrade `app/heuristics/handlers/constraints.py` to "understand" logic without an AI.

## OBJECTIVES
1. **Negative Constraint Logic**:
   - Build a parser that specifically targets negation words ("never", "do not", "avoid", "shouldn't").
   - Extract these sentences and strip the negation to create positive "Anti-Patterns" or keep them as "Negative Constraints" in a specific `### Restrictions` section.

2. **Dependency Mapping**:
   - Detect causal phrases ("...because...", "...so that...", "...in order to...").
   - Reformat these into `Rule: [Action] (Reason: [Justification])` format to preserve intent.

3. **Missing Information Detection**:
   - Identify references to undefined entities (e.g., "use the database" when no schema is provided).
   - Insert `[MISSING: Database Schema]` placeholders in the output to alert the user.

4. **Input/Output Mapping**:
   - Heuristically detect input data types (e.g., text, code, numbers) and required output actions.
   - Construct a pseudo-algorithm block: `Input: [Type] -> Process: [Action] -> Output: [Format]`.

## DELIVERABLES
- Enhanced `ConstraintHandler` with `detect_negations` and `detect_dependencies` methods.
- A `LogicAnalyzer` class that returns a list of "Missing Info" warnings.
- **CONSTRAINT**: Maximize recall. It's better to flag a potential missing item than miss it.
```

---

## Roadmap 3: The Quality Auditor (Static Analysis & Linter)

**Goal:** Create a "Linter" for prompts that scores clarity, safety, and prompt engineering best practices, providing immediate feedback in the Offline UI.

**Prompt for Agent:**
```markdown
# MISSION: BUILD THE OFFLINE PROMPT LINTER

You are a Lead QA Engineer and Security Researcher.
Your task is to build `app/heuristics/linter.py`, a comprehensive static analysis engine for prompts.

## OBJECTIVES
1. **Ambiguity Scoring ("Weasel Word Detector")**:
   - Create a dictionary of weak words ("maybe", "try to", "sort of", "briefly").
   - Calculate an "Ambiguity Score". If high, warn the user: "Command is too vague; use imperative verbs."

2. **Prompt Density Metric**:
   - Calculate the Information Density (Unique Informative Words / Total Words).
   - If density is low (too much fluff), trigger a "Telegraphic Style" recommendation.

3. **Advanced Safety Heuristics (Red Teaming)**:
   - Expand `RiskHandler` to include "Prompt Injection" patterns (e.g., "Ignore previous instructions", "System override").
   - Detect PII (Email, Phone, IP patterns) and auto-mask them in the preview.

4. **Conflict Detection**:
   - Detect mutually exclusive instructions (e.g., "Be detailed" vs "Be concise", "JSON" vs "Markdown").
   - Return a `conflicts` list in the analysis result.

## DELIVERABLES
- `PromptLinter` class with `lint(text) -> LintReport`.
- `LintReport` should contain: `score` (0-100), `warnings` (List), `safety_flags` (List).
- Integration into the `offline` route to show real-time "Health Bars" for the prompt.
- **CONSTRAINT**: Must run in <50ms. specific regex optimizations required.
```
