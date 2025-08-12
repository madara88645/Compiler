# Prompt Compiler App (promptc)

Compile messy prompts (TR/EN) into a strict IR (JSON) and generate System Prompt, User Prompt, Plan, and an Expanded Prompt for everyday use.

CI: ![CI](https://github.com/madara88645/Compiler/actions/workflows/ci.yml/badge.svg)

## Features
- Language (tr/en), domain guess with evidence
- IR fields: goals, tasks, inputs (interest/budget/format/level/duration), constraints, style, tone, output_format, length_hint, steps, examples, banned, tools, metadata
- Recency rule adds `web` tool + constraint
- Teaching mode (intent, level, duration) + mini quiz
- Deterministic and offline; JSON Schema validated; FastAPI API + Typer CLI

## Quickstart
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m pytest -q
```

### Run API
```powershell
uvicorn api.main:app --reload
```
Health: http://127.0.0.1:8000/health

### CLI
```powershell
# If script not found, use module form below
promptc compile "elon musk kimdir ve yapay zeka ile şu an ne yapıyor?"

python -m cli.main compile "teach me gradient descent in 15 minutes at intermediate level"
```

### cURL
```bash
curl -X POST http://127.0.0.1:8000/compile -H "Content-Type: application/json" -d '{"text":"arkadaşıma hediye öner futbol sever bütçe 1500-3000 tl tablo"}'
```

## What to copy into an LLM?
- Use System Prompt as system role
- Use User Prompt or Expanded Prompt as user message
- Plan and IR JSON are optional/internal

## Project Structure
```
app/ core models, heuristics, compiler, emitters
api/ FastAPI app
cli/ Typer CLI
schema/ JSON schema for IR
examples/ Sample prompts
tests/ Pytest suite
```

## Contributing
See CONTRIBUTING.md and CODE_OF_CONDUCT.md

## Security
See SECURITY.md

## License
MIT
