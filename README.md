# Prompt Compiler App (promptc)

Compile messy natural language prompts (TR/EN) into a structured Intermediate Representation (IR) and generate:
- System Prompt
- User Prompt
- Execution Plan

## Features
- Language (tr/en) and domain heuristics (ai/nlp, ai/ml, finance, physics, software, general) with evidence.
- IR extraction with goals, tasks, constraints, style, tone, output format, length hint, steps, examples, banned, tools, metadata.
- Recency detection keywords auto-injects `web` tool + constraint line.
- Conflict detection (simple heuristic) stored in metadata.conflicts.
- Deterministic & offline.
- FastAPI API + Typer CLI.
- JSON Schema validation tests.

## Install
```powershell
pip install -e .
```

## Run Tests
```powershell
pytest -q
```

## Run API
```powershell
uvicorn api.main:app --reload
```
Visit: http://127.0.0.1:8000/health

## CLI Usage
```powershell
promptc compile "elon musk kimdir ve yapay zeka ile şu an ne yapıyor?"
```

## Example Output (Recency Case)
```
IR.tools -> ["web"]
IR.constraints includes "Güncel bilgi gerektirir" line
```

## cURL Example
```bash
curl -X POST http://127.0.0.1:8000/compile -H "Content-Type: application/json" -d "{\"text\":\"elon musk kimdir ve yapay zeka ile şu an ne yapıyor?\"}"
```

## Project Structure
```
app/ models, heuristics, compiler, emitters
api/ FastAPI app
cli/ Typer CLI
schema/ JSON schema for IR
examples/ Sample prompts
tests/ Pytest suite
```

## JSON Schema
Located at `schema/ir.schema.json` and enforced in tests.

## Notes
Heuristics intentionally simple and transparent. Lists deduplicated, defaults applied when missing.
