# Prompt Compiler

![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

<p align="center">
  <img src="docs/images/cover.jpg" alt="Prompt Compiler Cover" width="100%">
</p>

**Prompt Compiler** turns vague requests into structured prompts, execution plans, and policy-checked workflows — so you can go from idea to safe, usable AI output in seconds.

It also ships a **PR Safety / Merge Readiness Layer**: paste an AI-agent PR and get a clear verdict — **merge, hold, split, or rebase** — before you merge it.

Try it now at [prcompiler.com](https://prcompiler.com) — or open [PR Safety](https://prcompiler.com/pr-safety) ([guide](docs/pr-safety.md)) · [VS Code extension](integrations/vscode-extension) · [GitHub artifacts](docs/pattern-library.md)

---

## What It Does

**Compile a request.** Type any request — a feature idea, a bug report, a research question — and Prompt Compiler produces:

- **System Prompt** — persona, role, constraints, output format
- **User Prompt** — structured task definition
- **Execution Plan** — step-by-step decomposition of coordinated tasks
- **Expanded Prompt** — ready to paste into any LLM, with domain-aware **key considerations** and decisive follow-up questions for recognized scenarios
- **Policy Layer** — risk level, allowed tools, execution mode, data sensitivity
- **Readiness Check** — a self-describing traffic light that tells you whether the compiled prompt is ready to run, honoring the compiled safety policy

The core pipeline is **offline and deterministic** — compilation needs no API key and no network — and is locked in place by a 1,700+ test suite with QA regression gates. Cloud features (optional) run server-side through OpenRouter only.

**Check a pull request.** Paste an AI-agent PR's title, description, and changed files into **PR Safety** and get a deterministic merge-readiness report:

- **Verdict** — `merge` · `hold` · `split` · `rebase`
- **Signals** — risky areas, test coverage, branch freshness, scope match
- **Recommendations** — plus a GitHub-ready Markdown export you can paste into the PR

It runs fully offline (no GitHub API, no AI calls, no sign-in) and never blocks a merge — it's advice for the human in the loop.

---

## Key Features

### Core Prompt Compiler

The engine analyzes your intent and produces the core output layers:

- **System Prompt**: persona, role, constraints, and output format rules for the target AI
- **User Prompt**: structured task definition derived from your input
- **Execution Plan**: decomposed steps based on your request — coordinated tasks ("do X and then Y") are split into ordered steps
- **Expanded Prompt**: a combined prompt ready to paste into chat-based LLMs, enriched with hand-curated **Key considerations** for recognized scenarios (SQL performance, file uploads, auth flows, timezones, browser downloads, payments, and more) and **decisive follow-up questions** a competent engineer would actually ask
- **Readiness Check**: a traffic-light banner that says whether the compiled prompt is ready to run and what would make it safer — it honors the compiled safety policy, so risky requests are never waved through

Switch between the output tabs in the UI to inspect each layer, and copy any result with one click.

<p align="center">
  <img src="docs/images/comp1.PNG" alt="Prompt Compiler - Main View" width="100%">
</p>

---

### Exploration Modes — adaptive latitude scheduling

Most prompt tools only tighten prompts. Prompt Compiler also schedules **how much latitude** the downstream agent should get, per plan step, derived from signals it already measures (problem cues in your own words, diagnostic intent, risk/policy):

| Mode | When it appears | What it tells the agent |
|---|---|---|
| `explore` | Diagnostic requests — "X is broken; help me fix it" | List plausible causes and test them against evidence before committing to a fix |
| `decide` | Multi-step diagnostic plans | Converge on one option by impact, effort, and risk — then stop exploring |
| `execute` | Concrete scoped work | Minimal deviation — no new requirements, dependencies, or scope |
| `verify` | Destructive / high-risk changes | Re-check edge cases and regressions before treating the result as done |

The Execution Plan tags steps in place (`1. [task] (explore) …`) and adds `[decide]` / `[verify]` steps where warranted, and the Expanded Prompt gains a **Working approach** section with per-mode directives (EN/TR/ES).

**Silence is a feature.** A clear request ("fix a typo") gains **zero** extra text — the scheduler engages only when the signals warrant it, and that guarantee is locked by a dedicated gate test suite. The machine-readable schedule also ships in the IR (`steps[].scheduling` with `mode`/`reason`/`confidence`, plus `metadata.uncertainty_profile`) for agent packs, analytics, and routing.

---

### PR Safety — Merge Readiness Layer

AI PR review bots create comments. **PR Safety** answers the question a human actually has: **should I merge this PR, or not?**

Paste a PR's title, description, and changed files (plus an optional "commits behind" value) and get a deterministic verdict with the signals behind it:

| Verdict | Meaning |
|---|---|
| **merge** | No blocking safety signals — proceed with normal review |
| **hold** | Risky area, missing tests, or scope mismatch — address before merging |
| **split** | Too large / spans too many top-level areas — break into smaller PRs |
| **rebase** | Branch is stale (far behind base) — update before merging |

Every report also surfaces **risky areas**, a **test-coverage** signal, **branch freshness**, **scope match**, and concrete **recommendations** — and can be copied or downloaded as a **GitHub-ready Markdown** report to drop straight into the PR (no auto-commenting; you stay in control).

**v1 is an offline, deterministic advisory.** It runs only on what you paste — no GitHub API, no AI calls, no sign-in — and never blocks a merge. Open it in the sidebar or at [`/pr-safety`](https://prcompiler.com/pr-safety); the [PR Safety guide](docs/pr-safety.md) has worked examples (docs-only, auth-risk, stale branch, split-needed), a `curl` recipe for `POST /pr-safety/report`, and an advisory [GitHub Action sketch](docs/pr-safety-github-action.md).

**CLI (no server):** analyze your local branch without starting the API — `promptc pr-safety --from-git` (or `python -m cli.main pr-safety --from-git` from the repo). See [docs/pr-safety.md](docs/pr-safety.md#cli-no-server-needed) for `--files-from`, `--format human|json|md`, and `--exit-code`.

**CLI (no server):** analyze your local branch without starting the API — `promptc pr-safety --from-git` (or `python -m cli.main pr-safety --from-git` from the repo). See [docs/pr-safety.md](docs/pr-safety.md#cli-no-server-needed) for `--files-from`, `--format human|json|md`, and `--exit-code`.

---

### Conservative Mode

The **Conservative** toggle controls how aggressively the compiler interprets your input.

| State | Behavior |
|---|---|
| **ON** (default) | Stays grounded in what you actually wrote. No invented libraries, fake APIs, or made-up requirements. Missing information leads to clarification instead of fabrication. |
| **OFF** | Expands more aggressively, fills gaps, and leans into richer prompt optimization. |

The toggle is available in both the **web app** and the **browser extension**, and its state is persisted locally.

<p align="center">
  <img src="docs/images/comp3offlineheuristics.PNG" alt="Offline Compiler - Heuristics Mode" width="80%">
</p>

---

### Policy-Aware Prompt Workflows

Prompt Compiler now also exposes a structured IR and policy layer for more sensitive or execution-heavy requests.

- **Risk Level**: `low`, `medium`, `high`
- **Execution Mode**: `advice_only`, `human_approval_required`, `auto_ok`
- **Data Sensitivity**: `public`, `internal`, `confidential`, `restricted`
- **Allowed / Forbidden Tools**
- **Sanitization Rules**

This is not a separate product. It is a new capability inside Prompt Compiler that helps you inspect risky requests before you run them downstream in coding, research, or automation flows.

---

### Agent Generator

Describe a role or autonomous task, and the **Agent Generator** produces a complete, constraint-driven system prompt for an AI agent.

- **Single Agent**: generates a focused, single-role agent prompt with boundary conditions
- **Multi-Agent Swarm**: toggle the multi-agent mode to generate a cooperative swarm-style prompt for specialized workers

#### Export Button

After generating an agent, the **Export** section can turn the output into framework-ready code:

| Framework | Output |
|---|---|
| **Claude SDK** | Python code using the `anthropic` client |
| **LangChain** | Python agent with `ChatPromptTemplate` |
| **LangGraph** | Python graph definition with node/edge structure |

<p align="center">
  <img src="docs/images/agent_generator.png" alt="Agent Generator" width="80%">
</p>

---

### Skill & Tool Generator

Describe a capability in plain English, and the **Skill Generator** translates it into a structured tool definition.

- Produces **Input Schema** and **Output Schema** in valid JSON
- Generates a stringified skill definition ready for LangChain, OpenAI functions, or custom agent frameworks

#### Export Button

After generating a skill, the **Export** section can wrap the output in framework-specific code:

| Format | Output |
|---|---|
| **LangChain Tool** | Python `@tool` function plus JSON schema |
| **Claude tool_use** | JSON config compatible with Anthropic's `tools` parameter |
| **Claude MCP Tool Stub** | Runnable FastMCP `server.py` + `README.md`, ready to register with Claude Code, Cursor, or Claude Desktop |

<p align="center">
  <img src="docs/images/skills_generator.png" alt="Skills Generator Interface" width="80%">
</p>

---

### Claude Agent Packs Beta

The **Agent Packs** sidebar turns a short project brief (project type, stack, goal) into a **runnable, repo-ready bundle of Claude assets** — not just a prompt. Pick a pack type, preview the files, copy individual snippets, or download the whole thing as a `.zip`.

This feature is currently in **beta**: it is designed to give you a strong starting point quickly, but you should still review every generated file before using it in production.

What the beta means in practice:

- **Fast scaffolding, not blind automation** - expect useful repo memory, settings, agents, and workflow files, then adjust them for your own policies and edge cases.
- **Best for early repo setup and internal experimentation** - especially when you want to bootstrap Claude Code conventions without hand-writing every asset.
- **Human review is required** - check prompts, permissions, deny rules, CI assumptions, and generated documentation before shipping.
- **A built-in install & review checklist** - after generation the UI shows a step-by-step checklist for placing each file in your repo and reviewing sensitive ones before you commit.
- **No Prompt Compiler API key prompts for visitors** - public web flows are meant to work without asking end users for `x-api-key`, `PROMPTC_SERVER_API_KEY`, or similar internal knobs.

Four pack types are available out of the box, all served from a single Claude-first endpoint:

| Pack Type | What It Emits | Use It For |
|---|---|---|
| **Project Pack** | `CLAUDE.md`, `.claude/settings.json`, `.github/workflows/claude.yml` | Bootstrapping Claude Code in a new repo with policy, deny rules, and CI on day one |
| **Subagent Bundle** | One or more `.claude/agents/<role>.md` files with `name`, `description`, and `tools` frontmatter | Giving Claude Code a team of specialized reviewers / builders that it can dispatch to |
| **PR Reviewer Pack** | A reviewer subagent + `.github/workflows/claude.yml` | Wiring Claude into pull request review automation |
| **MCP Tool Stub** | A FastMCP `server.py` + `README.md` scaffolded from a skill definition | Standing up an MCP server that exposes a custom tool to any MCP client |

**Risk-aware generation.** Each request takes a `risk_mode`:

| Mode | Behavior |
|---|---|
| `balanced` (default) | Sensible defaults: typical deny list, common allowed tools, gentle ask gates for destructive commands |
| `strict` | Tightens deny lists, narrows allowed tools, drops optimistic defaults — pick this when adopting Claude Code into a repo with sensitive data or untrusted contributors |

**Provider-agnostic core.** The pack generator is built around an `AgentPackAdapter` Protocol. Claude-specific logic lives in `app/adapters/claude_code.py`; the IR layer in `app/adapters/agent_packs.py` stays neutral. Cursor / Codex / other-provider adapters can plug in later without touching the core.

**API surface**:

```bash
# Generate the manifest (preview-friendly: file paths, contents, kinds, preview order)
curl -X POST https://api.example.com/agent-packs/claude \
  -H "content-type: application/json" \
  -d '{
    "project_type": "FastAPI service",
    "stack": "Python 3.12, FastAPI, PostgreSQL",
    "goal": "Add a Claude-reviewed PR workflow with deny rules for .env",
    "pack_type": "project-pack",
    "risk_mode": "strict"
  }'

# Same payload, returns a deflate-compressed .zip ready to drop into a repo
curl -X POST https://api.example.com/agent-packs/claude/download \
  -H "content-type: application/json" \
  -d '{...same body...}' \
  --output claude-project-pack.zip
```

**Repo-native adoption.** This repo eats its own dog food: the Compiler itself ships a `CLAUDE.md`, a hardened `.claude/settings.json` (denies `.env*`, `secrets/**`, `users.db`, `web/.env.local`; gates `git push`, `fly:`, `railway:` behind explicit confirmation), four ready-to-dispatch subagents in `.claude/agents/` (`compiler-architect`, `frontend-polisher`, `mcp-integrator`, `prompt-safety-reviewer`), and a `claude.yml` workflow for hosted Claude Code review on PRs.

---

### Token Optimizer

Compresses your prompt by roughly **20-30%** without losing meaning, logic, or variables. Useful near context-window limits.

<p align="center">
  <img src="docs/images/comp2tokenoptimizer.PNG" alt="Token Optimizer Interface" width="80%">
</p>

---

### Benchmark Playground

A/B test raw prompts against compiled versions:

- **Raw vs. Compiled** side-by-side comparison
- **Auto-Judge** scoring for relevance, quality, and clarity
- **Visual Metrics** including improvement percentages

<p align="center">
  <img src="docs/images/comp4benchmark.PNG" alt="Benchmark Playground Interface" width="80%">
</p>

---

### RAG & Knowledge Base

Upload project files such as PDF, Markdown, text, or code to ground Prompt Compiler in your own domain context.

- **Context Manager** for drag-and-drop reference files
- **Strategist/Critic flow** for injecting grounded context and catching hallucinated claims
- **Local SQLite-backed retrieval** for fast reuse without re-uploading

---

### GitHub Workflow Artifacts

Prompt Compiler can render deterministic markdown artifacts from natural language requests:

- **Issue Brief**
- **Implementation Checklist**
- **PR Review Brief**

Example:

```bash
python -m cli.main github render --type pr-review-brief --from-file prompt.txt
```

---

### VS Code Extension

The VS Code package lives in [`integrations/vscode-extension`](integrations/vscode-extension).

Start the backend before using the extension (default API URL is `http://127.0.0.1:8080`):

```bash
python -m uvicorn api.main:app --reload --port 8080
```

**Install today:**

- **From a `.vsix`** — download the `promptc-vscode-vsix` artifact from the latest [Publish VS Code Extension](https://github.com/madara88645/Compiler/actions/workflows/publish-vscode.yml) workflow run, then install via **Extensions: Install from VSIX...**
- **From source** — see [Local development](integrations/vscode-extension/README.md#local-development) in the extension README (`F5` / Extension Development Host)

**Once published** (after the Marketplace publisher is claimed and the first `vscode-v*` tag is pushed):

- **VS Code Marketplace** — [`madara88645.promptc-vscode`](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode)
- **Open VSX** (VSCodium / Cursor) — [`madara88645/promptc-vscode`](https://open-vsx.org/extension/madara88645/promptc-vscode)

Features:

- Commands: `PromptC: Compile Selection`, `PromptC: Compile File`, `PromptC: Recompile Last`
- Activity Bar sidebar for backend status, latest compile summary, history, and favorites
- Panel tabs: `Intent`, `Policy`, `Prompts`, `Raw JSON`
- Artifact actions: copy, insert into editor, save favorite
- Settings: `promptc.apiBaseUrl`, `promptc.conservativeMode`, `promptc.requestTimeoutMs`, `promptc.autoOpenPanel`, `promptc.historySize`

API keys are stored in VS Code secret storage, not workspace settings.

---

## Installation

### CLI (pip / pipx)

Install the command-line compiler directly from GitHub:

```bash
pipx install git+https://github.com/madara88645/Compiler.git   # recommended — isolated install
# or
pip install git+https://github.com/madara88645/Compiler.git
```

Then compile a prompt:

```bash
promptc compile "write a haiku about the sea"
promptc --version
```

> **Once published on PyPI**, you will also be able to install with:
>
> ```bash
> pipx install prcompiler        # recommended — isolated install
> # or
> pip install prcompiler
> ```

### From source (development)

```bash
git clone https://github.com/madara88645/Compiler.git
cd Compiler

# Backend: pyproject.toml is the source of truth
python -m pip install -e .[dev,docs]

# Frontend
cd web
npm ci
cd ..
```

### Environment Setup

```bash
cp .env.example .env
```

Core variables:

```env
OPENROUTER_API_KEY=sk-or-v1-your-actual-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-oss-20b
OPENROUTER_HTTP_REFERER=
OPENROUTER_TITLE=Prompt Compiler

# Prompt compiler mode: conservative (default) or default
PROMPT_COMPILER_MODE=conservative

# Optional internal auth hardening (public app routes do not ask visitors for Prompt Compiler API keys)
ADMIN_API_KEY=replace-me
PROMPTC_REQUIRE_API_KEY_FOR_ALL=false

# Optional RAG storage controls
PROMPTC_UPLOAD_DIR=.promptc_uploads
PROMPTC_RAG_ALLOWED_ROOTS=
```

Notes:

- Public app routes are intended to work without custom Prompt Compiler API keys.
- `OPENROUTER_API_KEY` is a server-side provider credential, not a value that visitors should type into the app.
- Prompt Compiler's cloud path is OpenRouter-only. Groq and legacy OpenAI fallback guidance should be treated as obsolete.
- If you set `PROMPTC_RAG_ALLOWED_ROOTS`, only files inside those roots can be ingested by path.

---

## Running the App

**Windows (one-click):** double-click `start_app.bat`

**Manual:**

```bash
# Terminal 1 - Backend
python -m uvicorn api.main:app --reload --port 8080

# Terminal 2 - Frontend
cd web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## How To Use

1. Type your idea, prompt, task, or workflow request into the input box.
2. Click **Generate**.
3. Check the **readiness banner** on the result — it tells you whether the compiled prompt is ready to run and why.
4. Review the output tabs: `Intent`, `System`, `User`, `Plan`, `Expanded`, `JSON`, `Quality`.
5. Use **Conservative** mode when you want grounded output.
6. If the task is sensitive, inspect the policy layer before using the result downstream.
7. Use Agent, Skill, Optimizer, Benchmark, and RAG surfaces as needed.

To check a pull request instead, open **PR Safety** in the sidebar, paste the PR's title, description, and changed files, then **Analyze PR** and read the verdict — copy the Markdown report into the PR if it's useful.

---

## Project Structure

```text
api/            FastAPI endpoints (compile, agent-generator, skills-generator, optimize, rag)
app/
  compiler.py       Core compiler pipeline
  emitters.py       Prompt rendering layer
  models_v2.py      IR v2 and policy contract
  llm_engine/       HybridCompiler and provider logic
  heuristics/       Offline parsing, safety, risk, and policy inference
  pr_safety/        Offline PR Safety analyzer (verdict + signals)
  rag/              SQLite FTS5 RAG index and retrieval
  testing/          Regression runner
  github_artifacts.py
web/
  app/
    page.tsx                    Main compiler UI
    pr-safety/                  PR Safety page + report proxy + Markdown export
    agent-packs/                Claude Agent Packs generator + install checklist
    agent-generator/            Agent Generator page
    skills-generator/           Skill Generator page
    benchmark/                  Benchmark Playground
    optimizer/                  Token Optimizer
    components/                 Shared UI components
cli/            CLI entrypoints
integrations/
  vscode-extension/
extension/      Browser extension
tests/          Offline-safe test suite
docs/           Product, pattern, and workflow docs
```

---

## Docs

- [`docs/pr-safety.md`](docs/pr-safety.md) — PR Safety usage guide, examples, and `curl` recipe
- [`docs/pr-safety-github-action.md`](docs/pr-safety-github-action.md) — advisory CI integration sketch
- [`docs/pattern-library.md`](docs/pattern-library.md)
- [`docs/promptc-safe-workflows.md`](docs/promptc-safe-workflows.md)
- [`examples/github/promptc-artifact.yml`](examples/github/promptc-artifact.yml)

---

## License

Copyright © 2026 Mehmet Özel. All rights reserved.

Licensed under the [Apache License 2.0](LICENSE).

For managed/hosted service inquiries: [mehmet.ozel2701@gmail.com](mailto:mehmet.ozel2701@gmail.com)

Self-hosting is free and always will be.
