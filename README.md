# Prompt Compiler App (promptc)

[![CI](https://github.com/madara88645/Compiler/actions/workflows/ci.yml/badge.svg)](https://github.com/madara88645/Compiler/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Compile messy prompts (Turkish/English) into a structured Intermediate Representation (JSON) and generate optimized System Prompt, User Prompt, Plan, and Expanded Prompt for everyday use with LLMs.

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
- **Language Detection**: Automatic language detection (Turkish/English) with domain guessing and evidence
- **Structured IR**: JSON Schema validated Intermediate Representation with fields: persona, role, goals, tasks, inputs (interest/budget/format/level/duration), constraints, style, tone, output_format, length_hint, steps, examples, banned, tools, metadata
- **Recency Rule**: Automatically adds `web` tool + constraints for time-sensitive queries
- **Teaching Mode**: Intelligent detection of learning intent with level, duration, analogy guidance, instructor persona, and mini quiz generation
- **Summary / Comparison / Variants**: Auto-detect summary requests (with optional bullet limits), structured multi-item comparisons (auto table), and multiple variant generation (2–10)
- **Extended Heuristics**: Risk flags (financial/health/legal), entity extraction, complexity score, ambiguous term detection with clarify questions, code request detection
- **Multiple Outputs**: Generates System Prompt, User Prompt, Plan, and Expanded Prompt for different use cases
- **Deterministic & Offline**: No external API calls, fully reproducible results
- **FastAPI + CLI**: Both REST API and command-line interface available

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
### API Server

Start the FastAPI server:

```bash
uvicorn api.main:app --reload
```

The API will be available at:
- **Health Check**: http://127.0.0.1:8000/health
- **API Documentation**: http://127.0.0.1:8000/docs (Swagger UI)

#### POST /compile
Compile a text prompt into structured IR and generated prompts.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/compile \
  -H "Content-Type: application/json" \
  -d '{"text":"arkadaşıma hediye öner futbol sever bütçe 1500-3000 tl tablo"}'
```

**Response:**
```json
{
  "ir": {"language": "tr", "domain": "shopping", "goals": ["arkadaşıma hediye öner"]},
  "system_prompt": "Persona: assistant\nRole: Helpful generative AI assistant...",
  "user_prompt": "Goals: arkadaşıma hediye öner...",
  "plan": "1. Identify football-related gift options",
  "expanded_prompt": "Generate clear suggestions..."
}
```

#### GET /health
```json
{"status": "ok"}
```

## Examples

The `examples/` directory contains sample prompts to test different features:

- **`example_en.txt`**: English prompt for structured output
- **`example_tr.txt`**: Turkish prompt with table format request  
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
  "language": "tr|en",           // Detected language
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
│   └── ir.schema.json    # IR format schema
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
- 🎯 **Consistent Prompting**: Need reproducible, structured prompts for LLM workflows
- 🌐 **Multi-language**: Working with Turkish and English prompts  
- 📚 **Teaching Content**: Creating educational content with automatic level detection
- 🛍️ **Structured Tasks**: Shopping recommendations, comparisons, planning
- ⏰ **Time-sensitive**: Queries that need current information (auto-adds web tool)
- 🔄 **Batch Processing**: Converting many natural prompts into structured format

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
- Detects level (beginner/intermediate/advanced) and adjusts constraints
- Detects duration (e.g. `15m`, `1h`) and adds time-bound constraint
- Rebuilds steps into a teaching sequence and injects a mini quiz scaffold

Example:
```bash
promptc "teach me binary search in 10 minutes beginner level"
```
Will set role to English instructor persona, add analogies + level + duration constraints and produce structured steps + quiz examples.

### General Task Enhancements
These features are automatically detected and stored in `metadata` (so the IR schema değişmedi):

#### 1. Summary Detection
Triggers on keywords: `tl;dr`, `summarize`, `summary`, `brief`.
Adds constraints:
- `Provide a concise summary`
- `Max N bullet points` (if "5 madde", "7 bullets" gibi ifade bulunursa)

Example:
```bash
promptc "summarize the text in 5 bullet points"
```
Metadata alanları:
- `summary`: `true|false`
- `summary_limit`: sayı (isteğe bağlı)

#### 2. Comparison Detection
Triggers on: `vs`, `karşılaştır`, `compare`, `versus`, `farkları`.
Heuristikle öğeleri ayrıştırır ("python vs go", "python ile go karşılaştır").
Ekler:
- Constraint: `Present a structured comparison`
- `output_format` otomatik `table` (markdown tablosu üretimi hedeflenir)
Metadata:
- `comparison_items`: list of extracted items

Example:
```bash
promptc "python vs go performans karşılaştır"
```

#### 3. Variant (Alternatif) Generation
Triggers on: `alternatif`, `alternatifler`, `alternatives`, `variants`, `seçenek`, `options`.
Sayı verilirse ("3 alternatif", "2 options") aralık 2–10 arasında normalize edilir; yoksa varsayılan 3.
- Constraint: `Generate N distinct variants`
Metadata:
- `variant_count`: N (>=1; 1 ise varyant modu aktif değildir)

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

All new fields live in metadata (schema remains stable).
```
Constraints örneği:
```
Present a structured comparison
Generate 3 distinct variants
```

> Not: Bu alanlar şimdilik IR `metadata` altında tutulur; ileride şema genişletilebilir.

### Recency Rule  
For time-sensitive queries, automatically adds web research capability:
```bash
promptc "latest developments in AI 2024"
# Automatically adds: web tool + "requires up-to-date info" constraint
```

### Domain Detection
Automatically detects and provides evidence for domain classification:
- **software**: Python, JavaScript, programming keywords
- **ai/ml**: machine learning, neural networks, AI keywords  
- **shopping**: budget, price, product keywords
- **general**: fallback for unspecified domains

### Language Support
- **Turkish (tr)**: Full support with Turkish system prompts and localized examples
- **English (en)**: Complete English language support
- **Auto-detection**: Based on input text analysis

## Contributing
See CONTRIBUTING.md and CODE_OF_CONDUCT.md

## Security
See SECURITY.md

## License
MIT
