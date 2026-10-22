# OpenRouter retirement audit — 21 October 2026

Base inspected: `996efc59085cefd131ffaa2b3d62efb276211133` (`main`). Open PRs were checked; none covered this migration. No production traffic or deployed environment settings were inspected.

## Dependency classification

| Surface | Evidence / behavior | Change |
| --- | --- | --- |
| `app/llm_engine/client.py` / `WorkerClient._call_api` | Actual SDK request path for cloud product features; default `openai/gpt-oss-20b`, configurable via env/model override | Preserve default; apply retirement policy to the effective request model only when destination hostname is `openrouter.ai` |
| `app/llm/base.py` / `ProviderConfig` | Generic provider configuration had bare `gpt-4o` default | Align new configurations with existing OpenRouter default `openai/gpt-oss-20b` |
| `app/llm/providers.py` / `OpenAIProvider` | Class name means OpenAI-compatible HTTP, but default endpoint/key are OpenRouter | Normalize exact known retiring short ids; warn before deadline; return actionable error without posting at/after deadline |
| `app/llm/factory.py` | Already defaults its OpenAI-compatible cloud configuration to GPT-OSS-20B | Preserve env/config overrides |
| `app/optimizer/models.py` / `OptimizationConfig` | `gpt-4o` default influences estimates and persisted run metadata, not necessarily the provider actually executing mutations | Set new configuration default to GPT-OSS-20B; deserialize existing explicit values unchanged |
| `app/optimizer/model_catalog.py` | Reviewed price/tokenizer snapshot, not a list of executed calls or a runtime model selector | Keep GPT-4o and mini rows and aliases for saved estimates; mark compatibility comment; refresh only GPT-OSS-20B price/date |
| `language_costs.py`, `estimator.py`, `costs.py` | Prompt/run estimates and accumulated estimated cost | Add retirement warnings to user-facing estimates; retain original legacy-model prices, never replacement prices |
| `web/app/benchmark/models.json` | Frontend model metadata snapshot; current defaults already GPT-OSS-20B | Match refreshed GPT-OSS-20B backend rates and verification date |
| Tests using GPT-4o strings | Offline fixtures for historical pricing, persistence, reporting and validation | Keep compatibility fixtures; add exact retirement/date/host-scope tests |
| `examples/openai_pipe.py` | Optional direct `OpenAI()` example, using `OPENAI_API_KEY`; not the default OpenRouter integration | Leave unchanged. This notice is not sufficient evidence to change a direct OpenAI integration. |
| CLI `--model` help | Suggested an obsolete GPT-4o identifier | Replace example with the supported cloud default |

All eight exact ids in the OpenRouter 19 October notice are recognized, together with their exact unqualified legacy spellings. The notification includes dated GPT-4o snapshots and OpenRouter BYOK. No family-prefix migration is used. This change does not establish that direct OpenAI requests retire on the same date.

## Compatibility policy

- New defaults use `openai/gpt-oss-20b`, matching current cloud behavior rather than introducing another model family.
- Existing explicit choices are not silently switched. Before 14 January 2027, a retiring short spelling is sent as its original provider-qualified id with a warning. At/after the deadline the request is rejected locally with a supported-model instruction, without spending an API call.
- Only the exact destination hostname `openrouter.ai` receives this policy. Explicit direct OpenAI or other compatible endpoints retain their supplied model ids. Proxy/custom domains cannot be identified reliably as OpenRouter and remain the operator's responsibility.
- Saved runs deserialize their original `model` strings unchanged. Legacy `gpt-4o` / `gpt-4o-mini` price aliases still describe those models, not a substituted model. Dated variants without a reviewed price remain unknown; no guessed price is added.
- Prompt and evolutionary-run estimates now warn about retirement. Estimates for old models can still be used as historical estimates after the deadline; this is not an availability claim.

## Models and costs

The Models API was retrieved on 21 October 2026. GPT-OSS-20B's base text rates were $0.018 input / $0.09 output per million tokens, replacing the September snapshot's $0.03 / $0.13 in both backend and frontend records. Other catalog records retain their own September verification dates; they have not been relabeled as current.

Candidate alternatives (USD per million input / output tokens):

| Model | Rates | Relevant compatibility |
| --- | --- | --- |
| `openai/gpt-oss-20b` | $0.018 / $0.09 | Existing default; JSON response format and current request behavior already supported. Lowest-change choice for Compiler. |
| `openai/gpt-6-luna` | $0.10 / $0.50 | Text/JSON/structured outputs; no temperature; optional reasoning supports `none`. Suitable candidate for bounded JSON tasks only after adapting Compiler's sampling parameters and testing outputs. Not substituted here. |
| `openai/gpt-5.6-luna` | $0.20 / $1.20 | Existing catalog/benchmark option; no temperature, optional reasoning. Its existing selection is preserved, but no new claim that all current Compiler requests are compatible is made. |
| `google/gemini-2.5-flash-lite` | $0.10 / $0.40 | JSON/structured outputs and temperature supported. Different model/provider behavior needs task-specific evaluation before changing defaults. |

Luna's catalog includes increased pricing above 272,000 prompt tokens; cached input and service tiers also vary. The existing static price estimator does not model all routing, long-context tiers or reasoning usage. Provider-reported usage/cost remains separate. Adding more flat-price aliases would hide this limitation, so no new Luna pricing entry or automatic migration was introduced.

Sources: [Models API](https://openrouter.ai/api/v1/models), [GPT-OSS-20B](https://openrouter.ai/openai/gpt-oss-20b), [GPT-6 Luna](https://openrouter.ai/openai/gpt-6-luna), [Luna endpoints](https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints), [GPT-5.6 Luna](https://openrouter.ai/openai/gpt-5.6-luna), [Gemini Flash Lite](https://openrouter.ai/google/gemini-2.5-flash-lite).

## Pre-existing limits kept out of this patch

`cli/commands/optimize.py` passes its model string as the factory's `config` positional argument. `get_provider` expects `ProviderConfig`, so an explicit CLI `--model` may fail initialization and fall back to mock; run-cost metadata can also differ from the provider's effective env-selected model. Resume reloads saved configuration. This is not fixed by changing a default and needs a separate focused CLI configuration/reporting change. No successful live CLI model migration is claimed.

No API key was available, so paid completions, JSON-output quality and production usage are unverified. The PR remains draft. Reviewers should explicitly replace retiring deployment/env selections before the deadline, then run an authenticated compile/optimize smoke check. No merge or deployment was performed.

## Validation

- `python -m pytest tests/ -q`: **2,758 passed, 5 skipped**, 30 existing collection/deprecation warnings; 152.56 seconds. Live provider tests are opt-in and were skipped.
- Focused provider/catalog/estimator suite: **114 passed, 5 skipped**. Additional retirement/evolution/report/API subset: **46 passed**. Final new retirement test file: **20 passed**. These overlap with the full suite and are not additional unique tests.
- `npm run test -- --run app/benchmark/page.test.tsx app/__tests__/optimizer-page.test.tsx`: **21 passed**, 2 test files.
- `npm run build`: passed, including TypeScript checks and static generation.
- Ruff checks on all changed Python files and `git diff --check`: passed.
- The first backend run failed because the environment's SOCKS proxy required `socksio`; installing it in the isolated test environment resolved those failures. No dependency manifest was changed for this environment-specific package.
- No authenticated upstream completion or production end-to-end check was run.
