# PromptC for VS Code

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/madara88645.promptc-vscode?label=VS%20Marketplace&logo=visualstudiocode)](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode)
[![Open VSX](https://img.shields.io/open-vsx/v/madara88645/promptc-vscode?label=Open%20VSX)](https://open-vsx.org/extension/madara88645/promptc-vscode)
[![Installs](https://img.shields.io/visual-studio-marketplace/i/madara88645.promptc-vscode?label=Installs)](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode)

Compile selected text or full files into structured prompts with policy visibility, directly inside VS Code.

> **Status:** Listings go live once the one-time publisher setup in [PUBLISHING.md](PUBLISHING.md) completes and a `vscode-v*` tag is pushed. Until then these badges will render as "no published version" — that's expected.

## Install

- **VS Code / VS Code Insiders** — search `PromptC` in the Extensions view, or install from the [Marketplace listing](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode).
- **VSCodium / Cursor / others** — install from [Open VSX](https://open-vsx.org/extension/madara88645/promptc-vscode).
- **From a `.vsix`** — download the artifact attached to the latest `Publish VS Code Extension` workflow run on GitHub, then `Extensions → ⋯ → Install from VSIX…`.

## Local development

1. **Start the backend** (from repo root):

   ```bash
   uvicorn app.main:app --port 8080
   ```

2. **Install the extension** locally:

   ```bash
   cd integrations/vscode-extension
   # Open VS Code in this folder, then press F5 to launch Extension Development Host
   # Or use: code --extensionDevelopmentPath="$(pwd)"
   ```

3. **Compile something:**
   - Open any file, select text (or leave empty for full file)
   - Run `Ctrl+Shift+P` > **PromptC: Compile Selection**
   - The PromptC Panel opens beside your editor with 4 tabs

4. **View results** in the panel:
   - **Intent** — domain, persona, detected intents
   - **Policy** — risk level, allowed/forbidden tools, execution mode
   - **Prompts** — system, user, plan, expanded prompts
   - **Raw JSON** — full compile response

## Commands

| Command | Description |
|---|---|
| `PromptC: Compile Selection` | Compile selected text (or full file) |
| `PromptC: Open Panel` | Open/reveal the result panel |

## Settings

| Setting | Default | Description |
|---|---|---|
| `promptc.apiBaseUrl` | `http://127.0.0.1:8080` | Backend API URL |
| `promptc.conservativeMode` | `true` | Grounded output (no hallucinated libs/APIs) |

## API Key

If the backend requires authentication, the extension prompts for an API key on first 401/403 response. The key is stored securely in VS Code secret storage — never in workspace settings.

## Running Tests

```bash
cd integrations/vscode-extension
node --test tests/client.test.mjs
```
