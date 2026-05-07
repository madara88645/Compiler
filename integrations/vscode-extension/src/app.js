const vscode = require("vscode");
const { fetchCompileResult, fetchHealth, normalizeCompileResponse } = require("./client");
const { getExtensionConfig } = require("./config");
const {
  ARTIFACT_TYPES,
  DEFAULT_API_BASE_URL,
  FAVORITES_STATE_KEY,
  HISTORY_STATE_KEY,
  SECRET_KEY,
} = require("./constants");
const { createFavoriteEntry, pushFavoriteEntry, sanitizeStoredFavorites } = require("./favorites-store");
const { createHistoryEntry, pushHistoryEntry, sanitizeStoredEntries } = require("./history-store");
const { historyEntryToPanelState, getArtifactOptions } = require("./model");
const { createPanelManager } = require("./panel-manager");
const { PromptCSidebarProvider } = require("./sidebar");
const { ensureHealthyBackend, requestCompileWithAuthRetry, buildDocsUrl } = require("./workflow");

function createExtensionApp(context) {
  const state = {
    history: sanitizeStoredEntries(context.workspaceState.get(HISTORY_STATE_KEY, [])),
    favorites: sanitizeStoredFavorites(context.globalState.get(FAVORITES_STATE_KEY, [])),
    currentEntry: null,
    connectionOk: false,
  };

  state.currentEntry = state.history[0] || null;

  const sidebarProvider = new PromptCSidebarProvider(getSidebarState);
  const treeView = vscode.window.createTreeView("promptcSidebar", {
    treeDataProvider: sidebarProvider,
    showCollapseAll: true,
  });
  const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBarItem.command = "promptc.compileSelection";
  statusBarItem.tooltip = "Compile the current selection with PromptC";
  statusBarItem.text = "$(symbol-keyword) PromptC";
  statusBarItem.show();

  const panelManager = createPanelManager(context, {
    onAction: async (message) => {
      if (message.action === "copy-artifact") {
        await copyArtifact(message.artifact);
        return;
      }
      if (message.action === "insert-artifact") {
        await insertArtifact(message.artifact);
        return;
      }
      if (message.action === "save-favorite") {
        await saveFavorite(message.artifact);
      }
    },
  });

  context.subscriptions.push(treeView, statusBarItem, { dispose: () => panelManager.dispose() });

  const commandRegistrations = [
    ["promptc.openPanel", () => panelManager.reveal(historyEntryToPanelState(state.currentEntry))],
    ["promptc.compileSelection", () => compileActiveEditor("selection")],
    ["promptc.compileFile", () => compileActiveEditor("file")],
    ["promptc.recompileLast", () => recompileLast()],
    ["promptc.checkConnection", () => checkConnection(true)],
    ["promptc.setApiKey", () => setApiKey()],
    ["promptc.clearApiKey", () => clearApiKey()],
    ["promptc.copyArtifact", (artifactType) => copyArtifact(artifactType)],
    ["promptc.insertArtifact", (artifactType) => insertArtifact(artifactType)],
    ["promptc.saveFavorite", (artifactType) => saveFavorite(artifactType)],
    ["promptc.openHistoryEntry", (entryId) => openHistoryEntry(entryId)],
    ["promptc.copyFavoriteEntry", (favoriteId) => copyFavoriteEntry(favoriteId)],
  ].map(([command, handler]) => vscode.commands.registerCommand(command, handler));

  context.subscriptions.push(...commandRegistrations);
  sidebarProvider.refresh();

  async function compileActiveEditor(scope) {
    const editor = getTargetEditor();
    if (!editor) {
      vscode.window.showWarningMessage("Open a file or selection before compiling with PromptC.");
      return;
    }

    const sourceText = getSourceText(editor, scope);
    if (!sourceText.trim()) {
      vscode.window.showWarningMessage("There is no text to compile.");
      return;
    }

    await compileText({
      sourceText,
      scope,
      documentUri: editor.document.uri.toString(),
    });
  }

  async function compileText({ sourceText, scope, documentUri = "" }) {
    const config = getExtensionConfig();
    const healthy = await ensureHealthyConnection(config.apiBaseUrl, config.requestTimeoutMs);
    if (!healthy) {
      return;
    }

    if (config.autoOpenPanel) {
      panelManager.reveal(historyEntryToPanelState(state.currentEntry));
    }

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "PromptC is compiling your request",
      },
      async () => {
        try {
          const response = await requestCompileWithAuthRetry({
            initialApiKey: await context.secrets.get(SECRET_KEY),
            promptForApiKey: () =>
              vscode.window.showInputBox({
                prompt: "PromptC API key",
                password: true,
                ignoreFocusOut: true,
                placeHolder: "Stored securely in VS Code secret storage",
              }),
            storeApiKey: (value) => context.secrets.store(SECRET_KEY, value),
            compile: ({ apiKey }) =>
              fetchCompileResult({
                baseUrl: config.apiBaseUrl,
                conservativeMode: config.conservativeMode,
                text: sourceText,
                timeoutMs: config.requestTimeoutMs,
                apiKey,
              }),
          });

          const normalized = normalizeCompileResponse(response);
          const entry = createHistoryEntry({
            sourceText,
            scope,
            documentUri,
            normalized,
          });

          state.currentEntry = entry;
          state.connectionOk = true;
          state.history = pushHistoryEntry(state.history, entry, config.historySize);
          await context.workspaceState.update(HISTORY_STATE_KEY, state.history);

          panelManager.reveal(historyEntryToPanelState(entry));
          statusBarItem.text = `$(symbol-keyword) PromptC ${entry.summary.riskLevel}`;
          sidebarProvider.refresh();
        } catch (error) {
          vscode.window.showErrorMessage(error?.message || "PromptC compile failed.");
        }
      }
    );
  }

  async function ensureHealthyConnection(baseUrl, timeoutMs) {
    const result = await ensureHealthyBackend({
      baseUrl,
      timeoutMs: Math.min(timeoutMs, 3000),
      fetchHealth,
    });

    state.connectionOk = result.ok;
    sidebarProvider.refresh();

    if (result.ok) {
      return true;
    }

    const choice = await vscode.window.showErrorMessage(
      "PromptC backend is unavailable. Start the API, update the base URL, or open the docs.",
      "Retry",
      "Open Settings",
      "Open API Docs"
    );

    if (choice === "Retry") {
      return ensureHealthyConnection(baseUrl, timeoutMs);
    }
    if (choice === "Open Settings") {
      await vscode.commands.executeCommand("workbench.action.openSettings", "promptc.apiBaseUrl");
    }
    if (choice === "Open API Docs") {
      await vscode.env.openExternal(vscode.Uri.parse(buildDocsUrl(baseUrl)));
    }

    return false;
  }

  async function checkConnection(showMessage) {
    const config = getExtensionConfig();
    const result = await ensureHealthyBackend({
      baseUrl: config.apiBaseUrl,
      timeoutMs: Math.min(config.requestTimeoutMs, 3000),
      fetchHealth,
    });
    state.connectionOk = result.ok;
    sidebarProvider.refresh();

    if (showMessage) {
      if (result.ok) {
        vscode.window.showInformationMessage(`PromptC backend is healthy at ${config.apiBaseUrl}.`);
      } else {
        vscode.window.showErrorMessage(`PromptC backend is unavailable at ${config.apiBaseUrl}.`);
      }
    }

    return result.ok;
  }

  async function setApiKey() {
    const apiKey = await vscode.window.showInputBox({
      prompt: "PromptC API key",
      password: true,
      ignoreFocusOut: true,
      placeHolder: "Stored securely in VS Code secret storage",
    });

    if (!apiKey) {
      return;
    }

    await context.secrets.store(SECRET_KEY, apiKey);
    vscode.window.showInformationMessage("PromptC API key saved securely.");
  }

  async function clearApiKey() {
    await context.secrets.delete(SECRET_KEY);
    vscode.window.showInformationMessage("PromptC API key cleared.");
  }

  async function recompileLast() {
    if (!state.currentEntry) {
      vscode.window.showWarningMessage("PromptC has no previous compile to rerun yet.");
      return;
    }

    await compileText({
      sourceText: state.currentEntry.sourceText,
      scope: state.currentEntry.scope,
      documentUri: state.currentEntry.documentUri,
    });
  }

  async function copyArtifact(artifactType) {
    const type = artifactType || (await pickArtifactType())?.type;
    if (!type || !state.currentEntry) {
      if (!state.currentEntry) {
        vscode.window.showWarningMessage("Run PromptC compile before copying an artifact.");
      }
      return;
    }
    await vscode.env.clipboard.writeText(state.currentEntry.artifacts[type] || "");
    vscode.window.showInformationMessage(`Copied PromptC ${type} artifact.`);
  }

  async function insertArtifact(artifactType) {
    const type = artifactType || (await pickArtifactType())?.type;
    const editor = getTargetEditor();
    if (!type || !state.currentEntry) {
      if (!state.currentEntry) {
        vscode.window.showWarningMessage("Run PromptC compile before inserting an artifact.");
      }
      return;
    }
    if (!editor) {
      vscode.window.showWarningMessage("Open an editor before inserting a PromptC artifact.");
      return;
    }

    await editor.edit((editBuilder) => {
      editBuilder.replace(editor.selection, state.currentEntry.artifacts[type] || "");
    });
  }

  async function saveFavorite(artifactType) {
    const type = artifactType || (await pickArtifactType())?.type;
    if (!type || !state.currentEntry) {
      if (!state.currentEntry) {
        vscode.window.showWarningMessage("Run PromptC compile before saving a favorite.");
      }
      return;
    }

    const favorite = createFavoriteEntry(state.currentEntry, type);
    state.favorites = pushFavoriteEntry(state.favorites, favorite);
    await context.globalState.update(FAVORITES_STATE_KEY, state.favorites);
    sidebarProvider.refresh();
    vscode.window.showInformationMessage(`Saved ${type} artifact to PromptC favorites.`);
  }

  async function openHistoryEntry(entryId) {
    const entry = state.history.find((item) => item.id === entryId);
    if (!entry) {
      return;
    }
    state.currentEntry = entry;
    panelManager.reveal(historyEntryToPanelState(entry));
    sidebarProvider.refresh();
  }

  async function copyFavoriteEntry(favoriteId) {
    const favorite = state.favorites.find((item) => item.id === favoriteId);
    if (!favorite) {
      return;
    }
    await vscode.env.clipboard.writeText(favorite.content);
    vscode.window.showInformationMessage(`Copied favorite ${favorite.artifactType} artifact.`);
  }

  async function pickArtifactType() {
    return vscode.window.showQuickPick(getArtifactOptions(), {
      placeHolder: "Choose a PromptC artifact",
    });
  }

  function getSourceText(editor, scope) {
    if (scope === "file") {
      return editor.document.getText();
    }
    const selectionText = editor.document.getText(editor.selection);
    return selectionText.trim() ? selectionText : editor.document.getText();
  }

  function getTargetEditor() {
    return vscode.window.activeTextEditor || vscode.window.visibleTextEditors[0];
  }

  function getSidebarState() {
    const config = getExtensionConfig();
    return {
      baseUrl: config.apiBaseUrl || DEFAULT_API_BASE_URL,
      connectionOk: state.connectionOk,
      connectionLabel: state.connectionOk ? "Backend connected" : "Backend not checked",
      latestLabel: state.currentEntry ? "Latest compile" : "No compile yet",
      latestDescription: state.currentEntry
        ? `${state.currentEntry.summary.domain} - ${state.currentEntry.summary.riskLevel}`
        : "Run PromptC on any file or selection",
      latestTooltip: state.currentEntry
        ? `${state.currentEntry.summary.requestId}\n${state.currentEntry.sourceText}`
        : "Compile a selection or file to populate the sidebar.",
      currentEntry: state.currentEntry,
      history: state.history,
      favorites: state.favorites,
      artifactTypes: ARTIFACT_TYPES,
    };
  }

  function getTestApi() {
    return {
      getCurrentEntry: () => state.currentEntry,
      getHistory: () => state.history,
      getFavorites: () => state.favorites,
      getLastPanelHtml: () => panelManager.getLastRenderedHtml(),
    };
  }

  return {
    getTestApi,
    dispose() {
      panelManager.dispose();
    },
  };
}

module.exports = {
  createExtensionApp,
};
