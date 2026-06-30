# Agent Packs output-value evaluation

Date: 2026-06-30

## Method

Each candidate surface was called directly through its offline Python path with six realistic developer inputs.
Every input was repeated three times. Outputs were judged skeptically as `ADDS_VALUE`, `NEUTRAL`, or
`WORSE_THAN_NOTHING`; an output only added value when it supplied correct, request-specific substance that a
developer could act on.

All 108 measured outputs were byte-stable across their three repetitions.

## Baseline scorecard

| Surface | Adds value | Neutral | Worse than nothing | Main defect |
|---|---:|---:|---:|---|
| Agent Generator | 0/6 | 0/6 | 6/6 | The no-key path returns the same API-key error for every request. |
| Skills Generator | 0/6 | 0/6 | 6/6 | The no-key path returns the same API-key error for every request. |
| **Agent Packs** | **0/6** | **0/6** | **6/6** | It converts generator errors into installable-looking, unrelated artifacts and labels them ready. |
| Token/Prompt Optimizer | 0/6 | 6/6 | 0/6 | It removes minor whitespace but does not improve realistic prompt substance. |
| PR Safety report | 4/6 | 2/6 | 0/6 | Useful risk/test guidance, with two noisy scope-mismatch signals. |
| RAG retrieval | 6/6 | 0/6 | 0/6 | Correct source ranked first for every query; lower results sometimes contain lexical noise. |

Agent Packs was selected because its failure is more dangerous than the explicit Agent/Skills errors: the user
receives a downloadable artifact that appears usable while containing false or unrelated instructions.

## Agent Packs baseline evidence

| Case | Requested artifact | Verdict | Specific defects |
|---|---|---|---|
| 1 | Strict FastAPI webhook project pack | WORSE_THAN_NOTHING | `CLAUDE.md` describes Prompt Compiler, the main agent is `.claude/agents/error.md`, and the runbook invents Next.js commands. |
| 2 | Next.js accessibility subagent | WORSE_THAN_NOTHING | The only agent is named `error`; the README tells the user to invoke that broken agent. |
| 3 | Python release PR reviewer | WORSE_THAN_NOTHING | The reviewer body is an API-key error and the checklist ignores release/publishing risk. |
| 4 | Read-only GitHub issue MCP stub | WORSE_THAN_NOTHING | Emits `FastMCP("error")`, an `error()` tool with no parameters, and an empty purpose. |
| 5 | Rust CLI project pack | WORSE_THAN_NOTHING | Repeats the Prompt Compiler FastAPI/Next.js runbook and points MCP at `integrations/mcp-server/server.py`. |
| 6 | Django query-performance subagent | WORSE_THAN_NOTHING | The only agent is `error` and contains no Django, query-count, or no-edit constraint. |

Representative repeated-run SHA-256 values:

- Agent/Skills error outputs: `d7fd10b...` / `6eb4b845...` for all six cases.
- Agent Packs case 1: `1ed7c258...` on runs 1–3.
- Agent Packs case 4: `7de968ff...` on runs 1–3.
- Agent Packs case 6: `2d477f72...` on runs 1–3.

## Passing threshold

The same six Agent Packs inputs must be rerun three times after the change. Completion requires:

- at least four of six cases to move from `WORSE_THAN_NOTHING` to clearly `ADDS_VALUE`;
- all repeated outputs to remain byte-stable;
- no generator error text, `error` agent/tool name, Prompt Compiler-specific project description, or invented local
  MCP server path in any artifact;
- project type, declared stack, requested goal, conservative constraints, and an actionable verification workflow
  to survive into each relevant artifact.

## Re-test result

The same six inputs were rerun three times after implementation.

| Case | Before | After | Value now added |
|---|---|---|---|
| 1 — FastAPI webhook project pack | WORSE_THAN_NOTHING | ADDS_VALUE | Carries Stripe/idempotency/billing scope into a tailored maintainer, safe project guidance, approval gates, and validation reporting. |
| 2 — Next.js accessibility subagent | WORSE_THAN_NOTHING | ADDS_VALUE | Produces a correctly named subagent with keyboard/focus scope, declared stack, conservative constraints, and install verification. |
| 3 — Python release PR reviewer | WORSE_THAN_NOTHING | ADDS_VALUE | Produces a read-only reviewer focused on publishing, tests, dependency drift, file evidence, and honest CI status. |
| 4 — GitHub issue MCP stub | WORSE_THAN_NOTHING | ADDS_VALUE | Emits `read_repository_issue(request: str)`, preserves the no-mutation rule, and documents inputs, output, TODOs, errors, and tests. |
| 5 — Rust CLI project pack | WORSE_THAN_NOTHING | ADDS_VALUE | Uses Rust/clap/cargo and dry-run filesystem tests; contains no FastAPI, Next.js, uvicorn, npm, or invented MCP server path. |
| 6 — Django performance subagent | WORSE_THAN_NOTHING | ADDS_VALUE | Preserves the query-count-before-editing workflow, stack, scope, and validation evidence contract. |

Result: **6/6 moved to `ADDS_VALUE`**, exceeding the required 4/6 threshold. All 18 outputs were byte-stable.

Repeated-run SHA-256 values:

- Case 1: `83bc4fa6...` on runs 1–3.
- Case 2: `a3d53174...` on runs 1–3.
- Case 3: `50343630...` on runs 1–3.
- Case 4: `c7c3b461...` on runs 1–3.
- Case 5: `4b2a7cbf...` on runs 1–3.
- Case 6: `5c6b5983...` on runs 1–3.

The regression suite in `tests/test_agent_packs_value.py` keeps the six cases reproducible and enforces request
specificity, deterministic output, conservative boundaries, removal of error artifacts, and absence of invented
Prompt Compiler paths.
