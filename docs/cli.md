# Prompt Compiler CLI reference

The `promptc` command turns natural-language requests into structured prompts, plans, and exportable artifacts. Install from PyPI (`pip install prcompiler` or `pipx install prcompiler`), or run from a dev checkout with `python -m cli.main` (examples below use `promptc`; substitute `python -m cli.main` when working from source).

```bash
promptc --help
promptc --version
```

## Top-level commands

### `version`

Print the installed package version.

```bash
promptc version
```

### `compile`

Compile prompt text into structured IR and rendered prompts (offline heuristics by default).

```bash
promptc compile "write a haiku about the sea" --quiet
```

### `compile-export`

Compile a prompt offline and write executable Markdown plus structured JSON to a directory.

```bash
promptc compile-export "build a login flow for a FastAPI app" --out-dir ./exports
```

### `batch`

Batch-compile every `.txt` file in a directory to JSON, Markdown, or YAML outputs.

```bash
promptc batch ./prompts --out-dir ./compiled --format json
```

### `validate`

Validate one or more IR JSON files against the Prompt Compiler schema.

```bash
promptc validate compiled/output.json
```

### `fix`

Suggest or apply automatic fixes for prompt validation issues.

```bash
promptc fix "teach me gradient descent" --diff
```

### `compare`

Compare two prompts side by side and show IR differences.

```bash
promptc compare "summarize this article" "write a one-paragraph summary of this article" --label-a Draft --label-b Revision
```

### `pack`

Export a single-file prompt pack (System / User / Plan / Expanded) for copy-paste.

```bash
promptc pack "debug flaky CI tests in a Python monorepo" --format md --out review-pack.md
```

### `json-path`

Read a value from a JSON file using dot-path syntax (supports list indexes).

```bash
promptc json-path compiled/output.json metadata.domain
```

### `diff`

Compare two JSON files with a unified diff (useful in CI or review workflows).

```bash
promptc diff before.json after.json --sort-keys
```

### `pr-safety`

Analyze a pull request for merge safety using offline heuristics (no GitHub API).

```bash
promptc pr-safety --title "Add auth middleware" --description "Adds session validation." app/auth.py tests/test_auth.py
```

## `rag` — local RAG (SQLite FTS5)

Lightweight on-machine retrieval over your own files.

| Subcommand | Description |
|---|---|
| `index` | Index files or folders into the local RAG database |
| `query` | Search the index (FTS, embeddings, or hybrid) |
| `pack` | Pack top matching chunks into a context window |
| `stats` | Show index statistics |
| `prune` | Remove stale or orphaned index entries |

```bash
promptc rag index ./docs --ext .md
promptc rag query "how does conservative mode work" --k 3
promptc rag pack "deployment runbook" --max-chars 2000
promptc rag stats --json
promptc rag prune
```

## `template` — template management

| Subcommand | Description |
|---|---|
| `list` | List available built-in and user templates |
| `show` | Show full details for a template ID |

```bash
promptc template list --tag code
promptc template show code-review
```

## `analytics` — prompt analytics

| Subcommand | Description |
|---|---|
| `record` | Record a prompt compilation in the analytics database |
| `summary` | Summarize metrics for a time window |
| `trends` | Show score trends over time |
| `domains` | Break down usage by domain |
| `list` | List recent prompt records |
| `stats` | Show overall database statistics |
| `clean` | Delete analytics records older than N days |

```bash
promptc analytics record prompts/onboarding.txt --task-type teaching
promptc analytics summary --days 7
promptc analytics trends --days 30 --json
promptc analytics domains --persona teacher
promptc analytics list --limit 5 --min-score 70
promptc analytics stats
promptc analytics clean --days 90 --force
```

## `history` — prompt history

| Subcommand | Description |
|---|---|
| `list` | List recent prompt history entries |
| `search` | Full-text search across history |
| `show` | Show one history entry by ID |
| `stats` | Show history database statistics |

```bash
promptc history list --limit 10
promptc history search "gradient descent"
promptc history show abc123
promptc history stats
```

## `test` — prompt testing suite

| Subcommand | Description |
|---|---|
| `run` | Run a YAML test suite against a prompt |

```bash
promptc test run tests/fixtures/demo_suite.yaml
```

## `optimize` — evolutionary prompt optimization

| Subcommand | Description |
|---|---|
| `run` | Optimize a prompt using test feedback (mock provider by default) |
| `resume` | Resume a previous optimization run |
| `history list` | List past optimization runs |
| `history show` | Show details for one run |

```bash
promptc optimize run prompts/draft.txt tests/fixtures/demo_suite.yaml --provider mock --generations 2
promptc optimize resume run-abc --suite tests/fixtures/demo_suite.yaml
promptc optimize history list --limit 5
promptc optimize history show run-abc
```

## `github` — GitHub artifact helpers

| Subcommand | Description |
|---|---|
| `render` | Render GitHub-friendly Markdown from natural-language intent |

Artifact types: `issue-brief`, `implementation-checklist`, `pr-review-brief`.

```bash
promptc github render --type pr-review-brief --from-file .github/PULL_REQUEST_TEMPLATE.md
```

## `plugins` — plugin utilities

| Subcommand | Description |
|---|---|
| `list` | List installed Prompt Compiler plugins |

```bash
promptc plugins list --json
```

## `profile` — settings profiles

Profiles are shared with the desktop UI (conservative mode, API base URL, etc.).

| Subcommand | Description |
|---|---|
| `list` | List saved profiles |
| `show` | Print a profile payload as JSON |
| `save` | Save a new profile (snapshots current UI settings by default) |
| `activate` | Set the active profile for the UI |
| `clear` | Clear the active profile |
| `delete` | Delete a profile by name |
| `rename` | Rename a profile |
| `export` | Export a profile to a portable JSON file |
| `import` | Import a profile from JSON |

```bash
promptc profile list
promptc profile show work
promptc profile save work
promptc profile activate work
promptc profile clear
promptc profile delete old-draft
promptc profile rename work work-laptop
promptc profile export work --output work-profile.json
promptc profile import work-profile.json
```

## Related docs

- [PR Safety guide](pr-safety.md)
- [PR Safety GitHub Action sketch](pr-safety-github-action.md)
- [Portable GitHub artifact workflow](../examples/github/promptc-artifact.yml)
- [MCP server setup](../integrations/mcp-server/README.md)
- [VS Code extension](../integrations/vscode-extension/README.md)
