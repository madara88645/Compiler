# Prompt Compiler App (promptc)

[![CI](https://github.com/madara88645/Compiler/actions/workflows/ci.yml/badge.svg)](https://github.com/madara88645/Compiler/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Compile messy natural language prompts (Turkish / English / Spanish) into a structured Intermediate Representation (IR JSON) and generate optimized System Prompt, User Prompt, Plan, and Expanded Prompt for everyday use with LLMs. (Project documentation below is now fully in English for consistency.)

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Command Line Interface (CLI)](#command-line-interface-cli)
  - [API Server](#api-server)
- [Examples](#examples)
- [Intermediate Representation (IR) Schema](#intermediate-representation-ir-schema)
- [What to copy into an LLM?](#what-to-copy-into-an-llm)
- [Project Structure](#project-structure)
- [Use Cases](#use-cases)
- [Development Setup](#development-setup)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Features
* **Language Detection**: Automatic detection (Turkish / English / Spanish) with domain guessing and evidence
* **Structured IR**: JSON Schema validated IR with: persona, role, goals, tasks, inputs (interest / budget / format / level / duration), constraints, style, tone, output_format, length_hint, steps, examples, banned, tools, metadata
* **Recency Rule**: Adds `web` tool + recency constraint for time-sensitive queries
* **Teaching Mode**: Detects learning intent; adds instructor persona, level/duration constraints, pedagogical steps, mini quiz scaffold, reputable sources constraint
* **Summary / Comparison / Variants**: Detects summary (with bullet limits), multi-item comparisons (auto switch to table), and variant generation (2–10 distinct variants)
* **Extended Heuristics**: Risk flags (financial / health / legal), entity extraction, complexity score, ambiguous terms -> clarification questions, code request detection
* **Awareness Extensions (new)**: Broader domain/persona/risk/ambiguous keyword coverage (e.g., cloud, security, resilient, secure, portfolio, compliance)
* **Diagnostics Mode**: Optional expanded prompt section (--diagnostics) surfacing risk flags, ambiguous terms, clarify questions
* **Clarification Questions Block**: Auto-added (before diagnostics) when ambiguity detected
* **Assumptions Block**: Adds missing detail filler policy, disclaimer (for risky domains), and variant differentiation rule
* **Multiple Outputs**: System Prompt, User Prompt, Plan, Expanded Prompt, plus raw IR JSON
* **Deterministic & Offline**: No external API calls; reproducible
* **API + CLI + Desktop UI**: FastAPI, Typer CLI, and Tkinter GUI
* **Version Endpoint & CLI**: `/version` API route and `promptc version` command for build visibility
* **Heuristic Version & IR Hash**: Each IR adds `metadata.heuristic_version` and short `metadata.ir_signature`
* **IR v2 (default)**: Rich IR with constraint objects (id/origin/priority), explicit intents, typed steps. CLI defaults to v2; use `--v1` for legacy. API includes `ir_v2` by default; send `{ "v2": false }` to get only v1.
* **Multi-language emitters (TR/EN/ES)**: System/User/Plan/Expanded prompts render localized section labels for supported languages
* **New CLI Flags**: `--json-only`, `--quiet`, `--persona` (override)
* **API Extra Fields**: `/compile` returns `processing_ms`, `request_id`, `heuristic_version`
* **Follow-up Questions**: Expanded Prompt ends with 2 generic next-step questions
* **PII Detection (new)**: Emails / phones / credit cards / IBAN -> `metadata.pii_flags` + privacy constraint
* **Domain Candidates (new)**: Alternative plausible domains surfaced in `metadata.domain_candidates`
* **Domain Confidence (new)**: Ratio of primary domain evidence to total + raw counts (`metadata.domain_confidence`, `metadata.domain_scores`)
* **Temporal & Quantity Extraction (new)**: Detects temporal signals (years, quarters, relative phrases) and numeric quantities with units -> `metadata.temporal_flags`, `metadata.quantities`
* **Structured Clarification Objects (new)**: Rich clarify entries with category + question -> `metadata.clarify_questions_struct`
* **Constraint Origins (new)**: Maps each constraint to its heuristic source -> `metadata.constraint_origins`
* **External Config Overrides (new)**: Optional YAML/JSON patterns file to extend domains, ambiguity, risk keywords without code changes

## Installation

### System Requirements
- Python 3.10 or higher
- pip package manager

### Quick Install
```bash
# Clone the repository
git clone https://github.com/madara88645/Compiler.git
cd Compiler

# Create virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies and the package
pip install -r requirements.txt
pip install -e .

# Verify installation
python -m pytest -q
promptc --help
```

### Run API
```powershell
uvicorn api.main:app --reload
```
Health: http://127.0.0.1:8000/health

## Usage

### Command Line Interface (CLI)

The CLI is the fastest way to compile prompts:

```bash
# Basic usage
promptc "teach me gradient descent in 15 minutes at intermediate level"

# Multiple word prompt (quotes recommended)
promptc "explain quantum computing concepts for beginners"

# With diagnostics (risk & ambiguity insights)
promptc --diagnostics "Analyze stock market investment strategy and optimize performance"
```

**Example Output:**
```json
{
  "language": "en",
  "role": "Helpful generative AI assistant",
  "domain": "general",
  "goals": ["teach me gradient descent in 15 minutes at intermediate level"],
  "tasks": ["teach me gradient descent in 15 minutes at intermediate level"],
  "inputs": {
    "level": "intermediate",
    "duration": "15m"
  },
  "constraints": [
    "Use a progressive, pedagogical flow from concepts to examples",
    "Provide sufficient detail for intermediate level",
    "Time-bound: target completion within 15m"
  ],
  "style": ["structured"],
  "tone": ["friendly"],
  "output_format": "markdown",
  "length_hint": "medium",
  "steps": [
    "Introduce core concepts simply",
    "Demonstrate with examples", 
    "Propose a short exercise",
    "Summarize and list resources"
  ]
}
```

### Desktop UI (Offline)

Launch the local desktop interface (no server required):

```powershell
python ui_desktop.py
```

Features:
- Enter prompt text and click Generate
- Toggle Diagnostics to include risk & ambiguity insights in the Expanded Prompt tab
- Toggle Trace to show heuristic trace lines
- Copy buttons per tab (System / User / Plan / Expanded / IR JSON)
- Extra tabs: IR v2 JSON and Trace
- Save... button to export combined Markdown or IR JSON (v1/v2)
- Summary header shows Persona, Complexity, Risk flags, Ambiguous terms (when diagnostics on)
- Light / Dark theme toggle (bottom button in toolbar row)
- Status line shows processing time and heuristic versions

Screenshots (dark & light):

| Light Theme | Dark Theme |
|-------------|------------|
| ![Light UI](docs/images/desktop_light.png) | ![Dark UI](docs/images/desktop_dark.png) |

> If images are missing, capture and add them under `docs/images/`.

### API Server

Start the FastAPI server:

```bash
uvicorn api.main:app --reload
```

The API provides:
* **Health Check**: http://127.0.0.1:8000/health
* **Version**: http://127.0.0.1:8000/version
* **Docs (Swagger)**: http://127.0.0.1:8000/docs

#### GET /version
Returns running package version.

```json
{"version": "0.0.0-dev"}
```

#### POST /compile
Compile a text prompt into structured IR and generated prompts.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d '{"text":"suggest a gift for my friend football fan budget 1500-3000 tl table"}'
```

**Response:**
```json
{
  "ir": {"language": "en", "domain": "shopping", "goals": ["suggest a gift for my friend"]},
  "system_prompt": "Persona: assistant\nRole: Helpful generative AI assistant...",
  "user_prompt": "Goals: suggest a gift for my friend...",
  "plan": "1. Identify football-related gift options",
  "expanded_prompt": "Generate clear suggestions...",
  "processing_ms": 11,
  "request_id": "a1b2c3d4e5f6",
  "heuristic_version": "2025.08.19-2"
}
```

IR v2 is returned by default. To request legacy-only IR v1:
```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d '{"text":"teach me binary search in 10 minutes beginner level", "v2": false}'
```
The default response includes `ir_v2` and `heuristic2_version`. See `schema/ir_v2.schema.json` for the IR v2 schema.

#### GET /health
```json
{"status": "ok"}
```

## Examples

The `examples/` directory contains sample prompts to test different features:

- **`example_en.txt`**: English prompt for structured output
- **`example_tr.txt`**: Turkish prompt with table format request (file name retained for legacy example)
- **`example_recency_tr.txt`**: Turkish prompt triggering recency rule (adds web tool)

Try them:
```bash
promptc "$(cat examples/example_en.txt)"
promptc "$(cat examples/example_tr.txt)"
```

## Intermediate Representation (IR) Schema

The tool converts natural language prompts into a structured JSON format following this schema:

```json
{
  "language": "tr|en|es",        // Detected language
  "persona": "assistant|teacher|researcher|coach|mentor", // High-level persona enum
  "role": "string",              // Natural language role text
  "domain": "string",            // Detected domain (general, shopping, etc)
  "goals": ["string"],           // Main objectives
  "tasks": ["string"],           // Specific tasks to accomplish
  "inputs": {                    // Extracted structured inputs
    "interest": "string",        // User interests
    "budget": "string",          // Budget constraints  
    "format": "string",          // Requested format
    "level": "string",           // Skill/knowledge level
    "duration": "string"         // Time constraints
  },
  "constraints": ["string"],     // Rules and limitations
  "style": ["string"],           // Communication style
  "tone": ["string"],            // Tone of voice
  "output_format": "markdown|json|yaml|table|text",
  "length_hint": "short|medium|long",
  "steps": ["string"],           // Execution steps
  "examples": ["string"],        // Example outputs
  "banned": ["string"],          // Forbidden content
  "tools": ["string"],           // Required tools (web, etc)
  "metadata": {                  // Additional info (extensible; includes persona_evidence, comparison_items, variant_count, summary flags)
    "conflicts": ["string"],
    "detected_domain_evidence": ["string"],
    "notes": ["string"]
  }
}
```

## What to copy into an LLM?
- **System Prompt**: Use as the system role/instructions
- **User Prompt**: Use as the main user message (concise)
- **Expanded Prompt**: Use for more detailed context (alternative to User Prompt)
- **Plan**: Optional, shows reasoning steps
- **IR JSON**: Optional, for debugging or advanced usage

## Project Structure

```
├── app/                    # Core application logic
│   ├── models.py          # Pydantic models (IR class)
│   ├── compiler.py        # Main compilation logic
│   ├── heuristics.py      # Language detection & domain guessing
│   └── emitters.py        # Prompt generation (system, user, plan, expanded)
├── api/                   # FastAPI REST API
│   └── main.py           # API endpoints and request/response models
├── cli/                   # Command-line interface  
│   └── main.py           # Typer CLI application
├── schema/               # JSON Schema validation
│   ├── ir.schema.json        # IR v1 format schema
│   └── ir_v2.schema.json     # IR v2 format schema (preview)
├── examples/             # Sample prompts for testing
│   ├── example_en.txt    # English example
│   ├── example_tr.txt    # Turkish example
│   └── example_recency_tr.txt  # Recency rule example
├── tests/                # Pytest test suite
│   ├── test_language_domain.py    # Language detection tests
│   ├── test_teaching_*.py         # Teaching mode tests
│   ├── test_emitters.py          # Prompt generation tests
│   └── ...                       # Other feature tests
├── requirements.txt      # Python dependencies
├── pyproject.toml       # Project configuration
└── README.md           # This file
```

## Use Cases

**When to use promptc:**
* 🎯 **Consistent Prompting**: Reproducible, structured prompts for LLM pipelines
* 🌐 **Multi-language TR/EN/ES**: Automatic language adaptation
* 📚 **Teaching Content**: Educational flows with pedagogy enhancements
* 🛍️ **Structured Tasks**: Shopping, comparisons, planning, summarization
* ⏰ **Time-sensitive**: Auto web tool addition when recency detected
* 🔄 **Batch Processing**: Convert many raw prompts into clean standardized structure

**What promptc outputs:**
- **System Prompt**: For LLM system instructions
- **User Prompt**: Clean, structured user message
- **Plan**: Step-by-step execution plan
- **Expanded Prompt**: Detailed context for complex tasks
- **IR JSON**: Machine-readable intermediate representation

## Development Setup

For contributors and advanced users:

```bash
# Clone and setup
git clone https://github.com/madara88645/Compiler.git
cd Compiler
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows

# Install in development mode
pip install -r requirements.txt
pip install -e .

# Install development dependencies
pip install pytest black flake8

# Run tests
python -m pytest -v

# Run tests with coverage
python -m pytest --cov=app --cov=api --cov=cli

# Format code (optional)
black app/ api/ cli/ tests/

# Lint code (optional)  
flake8 app/ api/ cli/
```

## Troubleshooting

### Common Issues

**Q: `promptc` command not found**
```bash
# Use module form instead:
python -m cli.main "your prompt here"

# Or reinstall in editable mode:
pip install -e .
```

**Q: Tests failing**
```bash
# Make sure all dependencies are installed:
pip install -r requirements.txt

# Run specific test:
python -m pytest tests/test_language_domain.py -v
```

**Q: API server won't start**
```bash
# Check if port 8000 is in use:
uvicorn api.main:app --port 8001

# Or use different host:
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Q: Turkish characters not displaying correctly**
- Ensure your terminal supports UTF-8 encoding
- On Windows, use Windows Terminal or PowerShell 7+

## Advanced Features

### Teaching Mode Detection
The compiler automatically detects educational intent and enhances prompts:
```bash
promptc "teach me machine learning in 1 hour for beginners"
# Automatically adds: level detection, time constraints, structured steps, mini quiz
```

#### Teaching Mode Details
When a learning / teaching intent is detected (keywords like *teach, explain*):
- Role changes to an expert instructor persona (English only in examples)
- Adds progressive pedagogical flow constraint
- Adds analogy usage constraint
- Adds reputable source recommendations constraint
- Detects level (beginner/intermediate/advanced) and adjusts constraints
- Detects duration (e.g. `15m`, `1h`) and adds time-bound constraint
- Rebuilds steps into a teaching sequence and injects a mini quiz scaffold

Example:
```bash
promptc "teach me binary search in 10 minutes beginner level"
```
Will set role to English instructor persona, add analogies + level + duration constraints and produce structured steps + quiz examples.

### General Task Enhancements
These features are automatically detected and stored in `metadata` (so the IR schema does not change):

#### 1. Summary Detection
Triggers on keywords: `tl;dr`, `summarize`, `summary`, `brief`.
Adds constraints:
- `Provide a concise summary`
- `Max N bullet points` (if a phrase like "5 bullet points" appears)

Example:
```bash
promptc "summarize the text in 5 bullet points"
```
Metadata fields:
- `summary`: `true|false`
- `summary_limit`: integer (optional)

#### 2. Comparison Detection
Triggers on: `vs`, `compare`, `versus`.
Extracts items heuristicly ("python vs go", "python vs go vs rust").
Adds:
- Constraint: `Present a structured comparison`
- `output_format` auto `table` (targets a markdown table)
Metadata:
- `comparison_items`: list of extracted items

Example:
```bash
promptc "python vs go performance comparison"
```

#### 3. Variant Generation
Triggers on: `alternatives`, `variants`, `options`.
If a number is provided ("3 variants", "2 options") it's clamped 2–10; otherwise default 3.
- Constraint: `Generate N distinct variants`
Metadata:
- `variant_count`: N (>=1; if 1 then variant mode is effectively off)

Example:
```bash
promptc "summarize the text in 7 bullet points and give 2 variants"
```

#### Combined Example
```bash
promptc "python vs go performance compare give 3 alternatives"
}

## Extended Heuristics

The compiler enriches metadata and constraints with additional safety and clarity signals:

| Feature | Detection | Effect |
|---------|-----------|--------|
| Risk Flags | financial / health / legal keywords | Adds general-info (non-professional advice) constraint |
| Entities | Capitalized tokens & tech patterns | Stored in metadata.entities |
| Complexity | Length + concept signals | metadata.complexity = low/medium/high |
| Ambiguous Terms | optimize, improve, better, efficient, scalable, fast, robust | Clarify constraint + metadata.ambiguous_terms |
| Clarify Questions | From ambiguous terms list | metadata.clarify_questions (up to 5) |
| Code Request | code/snippet/python/function terms | Adds inline comments constraint + metadata.code_request |

All new fields live in metadata (schema remains stable). Recently expanded coverage adds cloud domain patterns, resiliency/security ambiguous terms, extended risk terms (portfolio, compliance, diagnosis), and richer persona triggers (workshop, accountability, growth).

### Heuristic Version & IR Signature
Each IR embeds a human-readable `heuristic_version` and a deterministic short hash `ir_signature` (first 12 chars of SHA-256 over normalized IR). Useful for caching and diffing.

### Temporal & Quantity Signals
Automatically extracts:
- Years (2023, 2024, etc), quarters (Q1, Q2 ...), months, relative phrases ("this month", "last year") → `metadata.temporal_flags`
- Quantities with units (e.g. `10m`, `15 minutes`, `3 hours`, `5 items`, ranges like `1500-3000 tl`) → `metadata.quantities`

### Structured Clarification Objects
`metadata.clarify_questions_struct` provides a list of objects: `{ "term": "scalable", "category": "performance", "question": "What scale target (users, rps, region) is expected?" }` enabling richer UI rendering.

### Constraint Origins
`metadata.constraint_origins` maps each normalized constraint string to the heuristic source (`teaching`, `summary`, `recency`, `risk_flags`, etc) for transparency and debugging.

### External Config Overrides
You can drop a `patterns.yml` (or `.json`) to extend / override domain patterns, ambiguous terms (with categories), and risk keywords at runtime—no code change needed.

### CLI New Flags
```powershell
promptc --json-only "summarize abstract transformer tokenization outline"
promptc --quiet "secure resilient scalable api design"
promptc --persona teacher "explain recursion in 10 minutes"
```

### API Extra Fields
`processing_ms` = server latency (ms), `request_id` = short UUID slice, `heuristic_version` mirrors IR metadata.

### Follow-up Questions Block
Expanded Prompt concludes with 2 generic future-oriented follow-up questions (language-aware) to guide refinement.

### Trace Mode
You can request a heuristic trace that lists which signals were detected and their counts/scores.

CLI examples:
```powershell
promptc --trace --json-only "cloud portfolio optimization this month"
promptc --trace "secure resilient scalable api design"
```
API example request body:
```json
{ "text": "secure resilient scalable api design", "trace": true }
```
Response includes a `trace` array:
```json
"trace": [
  "heuristic_version=2025.08.20-1",
  "language=en",
  "persona=assistant",
  "domain=cloud (2 evid)",
  "domain_evidence:cloud:aws,cloud:serverless",
  "ambiguous_terms=secure,resilient,scalable",
  "pii_flags=email",
  "domain_candidates=cloud,software",
  "domain_conf=0.67",
  "domain_scores=cloud:2,software:1",
  "variant_count=1",
  "complexity=medium",
  "ir_signature=abcdef123456"
]
```
