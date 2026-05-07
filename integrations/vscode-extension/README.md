# PromptC for VS Code

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/madara88645.promptc-vscode?label=VS%20Marketplace&logo=visualstudiocode)](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode)
[![Open VSX](https://img.shields.io/open-vsx/v/madara88645/promptc-vscode?label=Open%20VSX)](https://open-vsx.org/extension/madara88645/promptc-vscode)
[![Installs](https://img.shields.io/visual-studio-marketplace/i/madara88645.promptc-vscode?label=Installs)](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode)

Compile selected text or full files into structured prompts with policy visibility, directly inside VS Code.

> **Status:** Listings go live once the one-time publisher setup in [PUBLISHING.md](PUBLISHING.md) completes and a `vscode-v*` tag is pushed. Until then these badges will render as "no published version" and that is expected.

## Install

- **VS Code / VS Code Insiders** - search `PromptC` in the Extensions view, or install from the [Marketplace listing](https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode).
- **VSCodium / Cursor / others** - install from [Open VSX](https://open-vsx.org/extension/madara88645/promptc-vscode).
- **From a `.vsix`** - download the artifact attached to the latest `Publish VS Code Extension` workflow run on GitHub, then install it from the VS Code Extensions menu.

## Local development

1. **Start the backend** from the repo root:

   ```bash
   python -m uvicorn api.main:app --reload --port 8080
   ```

2. **Install extension dependencies**:

   ```bash
   cd integrations/vscode-extension
   npm ci
   ```

3. **Launch the extension host**:
   - Open this folder in VS Code and press `F5`
   - Or run `code --extensionDevelopmentPath="$(pwd)"`

4. **Compile something**:
   - Open any file and either select text or leave the selection empty
   - Run `PromptC: Compile Selection` or `PromptC: Compile File`
   - The PromptC Activity Bar view and PromptC Panel update together

## Daily workflow

- Use the **PromptC** Activity Bar view for backend status, latest compile summary, history, and favorites.
- Use the panel for detailed inspection across `Intent`, `Policy`, `Prompts`, and `Raw JSON`.
- Use the artifact buttons to **Copy**, **Insert**, or **Favorite** the latest `System`, `User`, `Plan`, and `Expanded` outputs.
- If the backend is down, PromptC offers **Retry**, **Open Settings**, and **Open API Docs** actions before running compile requests.

## Commands

| Command | Description |
|---|---|
| `PromptC: Compile Selection` | Compile the current selection, or the full file when nothing is selected |
| `PromptC: Compile File` | Always compile the full active file |
| `PromptC: Open Panel` | Reveal the PromptC result panel |
| `PromptC: Recompile Last` | Re-run the latest PromptC request |
| `PromptC: Check Connection` | Ping the configured backend `/health` endpoint |
| `PromptC: Set API Key` | Store an API key in VS Code secret storage |
| `PromptC: Clear API Key` | Delete the stored API key |
| `PromptC: Copy Artifact` | Copy the latest system, user, plan, or expanded artifact |
| `PromptC: Insert Artifact` | Insert the latest artifact into the current editor |
| `PromptC: Save Favorite` | Save the latest artifact for reuse from the sidebar |

## Settings

| Setting | Default | Description |
|---|---|---|
| `promptc.apiBaseUrl` | `http://127.0.0.1:8080` | Backend API URL |
| `promptc.conservativeMode` | `true` | Request grounded output instead of aggressive expansion |
| `promptc.requestTimeoutMs` | `30000` | API request timeout in milliseconds |
| `promptc.autoOpenPanel` | `true` | Automatically reveal the panel after a successful compile |
| `promptc.historySize` | `20` | Workspace-local compile history size |

## API Key

If the backend requires authentication, the extension prompts for an API key on the first `401` or `403` response. The key is stored securely in VS Code secret storage, never in workspace settings.

## Running Tests

```bash
cd integrations/vscode-extension
npm run test:unit
npm run test:integration
npm run package
```
