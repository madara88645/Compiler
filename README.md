# PromptC Intent Compiler

![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

<p align="center">
  <img src="docs/images/comp1.PNG" alt="PromptC Intent Compiler" width="100%">
</p>

PromptC is evolving from a general prompt tool into an open-source, security-aware intent compiler for developers.

Natural language intent goes in. Structured prompts, explicit execution policy, and reusable workflow artifacts come out.

---

## Why PromptC

PromptC compiles intent into:

- **IR-first structure** for downstream tooling
- **Policy visibility** for risky or sensitive requests
- **Prompt packs** for direct LLM usage
- **Workflow artifacts** for GitHub and developer loops
- **Regression-friendly outputs** for testing behavior over time

The main thesis is now:

> `natural language intent -> structured IR -> visible policy -> reusable workflow artifact`

---

## Core Features

### Intent Compiler Core

The compiler analyzes a request and produces:

- **System Prompt**: persona, role, and behavioral rules
- **User Prompt**: cleaned task definition
- **Execution Plan**: decomposed steps
- **Expanded Prompt**: combined prompt ready for chat-based LLMs
- **Policy Envelope**: risk level, execution mode, data sensitivity, tool bounds, sanitization rules

### Security-Aware Policy Inference

PromptC treats policy as a first-class part of the IR:

- **Risk Level**: `low`, `medium`, `high`
- **Execution Mode**: `advice_only`, `human_approval_required`, `auto_ok`
- **Data Sensitivity**: `public`, `internal`, `confidential`, `restricted`
- **Allowed / Forbidden Tools**
- **Sanitization Rules**

This turns PromptC into an inspectable intent compiler rather than a prompt-only optimizer.

### Conservative Mode

The **Conservative** toggle keeps output grounded in the original request:

- no invented details
- no hallucinated APIs or libraries
- short inputs stay short
- missing information triggers clarification instead of fabrication

### Intent Regression Runner

The CLI test runner can validate:

- output content
- compiled IR
- inferred policy
- risk thresholds
- execution mode
- expected tool and sanitization rules

### GitHub Workflow Artifacts

PromptC can render deterministic markdown artifacts from natural language intent:

- **Issue Brief**
- **Implementation Checklist**
- **PR Review Brief**

Example:

```bash
python -m cli.main github render --type pr-review-brief --from-file prompt.txt
```

### VS Code Extension MVP

The new VS Code package lives in [`integrations/vscode-extension`](integrations/vscode-extension):

- `PromptC: Compile Selection`
- `PromptC: Open Intent Panel`
- Tabs: `Intent`, `Policy`, `Prompts`, `Raw JSON`
- Settings: `promptc.apiBaseUrl`, `promptc.conservativeMode`
- API keys stored in VS Code secret storage, not settings JSON

---

## Secondary Surfaces

PromptC still includes additional surfaces that now sit behind the core intent-compiler story:

- Agent Generator
- Skill & Tool Generator
- Token Optimizer
- Benchmark Playground
- RAG & Knowledge Base

These remain useful, but they are now secondary to the main intent-compiler positioning.

---

## Installation

```bash
git clone https://github.com/madara88645/Compiler.git
cd Compiler

# Backend
pip install -r requirements.txt

# Frontend
cd web && npm install && cd ..
```

### Environment Setup

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-your-actual-key
OPENAI_BASE_URL=https://api.openai.com
GROQ_API_KEY=gsk_your_groq_key
PROMPT_COMPILER_MODE=conservative
```

---

## Running the App

```bash
# Terminal 1
python -m uvicorn api.main:app --reload --port 8080

# Terminal 2
cd web && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## How To Use

1. Type your intent in the web app or select text in VS Code.
2. Click **Generate** or run **Compile Selection**.
3. Inspect the **Policy** view before running anything downstream.
4. Copy prompts or render GitHub artifacts from the CLI.
5. Use **Conservative Mode** when you want grounded, low-hallucination output.

---

## Project Structure

```text
api/            FastAPI endpoints
app/
  compiler.py       Core compiler pipeline
  models_v2.py      IR v2 and policy contract
  testing/          Regression runner
  github_artifacts.py
  heuristics/       Offline inference handlers
web/            Next.js app
cli/            CLI entrypoints
integrations/
  vscode-extension/
extension/      Browser extension
tests/          Python test suite
docs/           Positioning and pattern docs
```

---

## Docs

- [`docs/pattern-library.md`](docs/pattern-library.md)
- [`docs/why-promptc-is-an-intent-compiler.md`](docs/why-promptc-is-an-intent-compiler.md)
- [`examples/github/promptc-artifact.yml`](examples/github/promptc-artifact.yml)

---

## License

Copyright © 2026 Mehmet Özel.

Licensed under the [Apache License 2.0](LICENSE).
