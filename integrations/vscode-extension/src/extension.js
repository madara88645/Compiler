const vscode = require("vscode");
const { fetchCompileResult, normalizeCompileResponse } = require("./client");
const { renderPanelHtml } = require("./panel");

const SECRET_KEY = "promptc.apiKey";

let panelInstance = null;
let lastState = null;

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("promptc.openPanel", () => {
      const panel = getOrCreatePanel(context);
      panel.webview.html = renderPanelHtml(lastState);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("promptc.compileSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("Open a file or selection before compiling with PromptC.");
        return;
      }

      const selectionText = editor.document.getText(editor.selection);
      const sourceText = selectionText.trim() ? selectionText : editor.document.getText();

      if (!sourceText.trim()) {
        vscode.window.showWarningMessage("There is no text to compile.");
        return;
      }

      const panel = getOrCreatePanel(context);
      panel.webview.html = renderPanelHtml(lastState);

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "PromptC is compiling your request",
        },
        async () => {
          const config = vscode.workspace.getConfiguration("promptc");
          const baseUrl = config.get("apiBaseUrl", "http://127.0.0.1:8080");
          const conservativeMode = config.get("conservativeMode", true);

          try {
            const response = await requestCompile(context, {
              baseUrl,
              conservativeMode,
              text: sourceText,
            });
            lastState = normalizeCompileResponse(response);
            panel.webview.html = renderPanelHtml(lastState);
          } catch (error) {
            vscode.window.showErrorMessage(error.message || "PromptC compile failed.");
          }
        }
      );
    })
  );
}

async function requestCompile(context, { baseUrl, conservativeMode, text }) {
  let apiKey = await context.secrets.get(SECRET_KEY);

  try {
    return await fetchCompileResult({ baseUrl, text, conservativeMode, apiKey });
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      apiKey = await vscode.window.showInputBox({
        prompt: "PromptC API key",
        password: true,
        ignoreFocusOut: true,
        placeHolder: "Stored securely in VS Code secret storage",
      });

      if (!apiKey) {
        throw new Error("PromptC request requires an API key.");
      }

      await context.secrets.store(SECRET_KEY, apiKey);
      return fetchCompileResult({ baseUrl, text, conservativeMode, apiKey });
    }

    throw error;
  }
}

function getOrCreatePanel(context) {
  if (panelInstance) {
    panelInstance.reveal(vscode.ViewColumn.Beside);
    return panelInstance;
  }

  panelInstance = vscode.window.createWebviewPanel(
    "promptcIntentPanel",
    "PromptC Panel",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );

  panelInstance.onDidDispose(
    () => {
      panelInstance = null;
    },
    null,
    context.subscriptions
  );

  panelInstance.webview.html = renderPanelHtml(lastState);
  return panelInstance;
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
