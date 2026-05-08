const vscode = require("vscode");
const { PANEL_TAB_STATE_KEY } = require("./constants");
const { createEmptyPanelState } = require("./model");
const { renderPanelHtml } = require("./panel");

function createPanelManager(context, handlers) {
  let panelInstance = null;
  let lastRenderedHtml = "";
  let lastState = createEmptyPanelState();
  let activeTab = context.workspaceState.get(PANEL_TAB_STATE_KEY, "intent");

  function render(state = lastState) {
    lastState = state || createEmptyPanelState();
    if (!panelInstance) {
      return;
    }
    lastRenderedHtml = renderPanelHtml(lastState, { activeTab });
    panelInstance.webview.html = lastRenderedHtml;
  }

  function getOrCreatePanel() {
    if (panelInstance) {
      panelInstance.reveal(vscode.ViewColumn.Beside);
      render(lastState);
      return panelInstance;
    }

    panelInstance = vscode.window.createWebviewPanel("promptcIntentPanel", "PromptC Panel", vscode.ViewColumn.Beside, {
      enableScripts: true,
      retainContextWhenHidden: true,
    });

    panelInstance.onDidDispose(
      () => {
        panelInstance = null;
      },
      null,
      context.subscriptions
    );

    panelInstance.webview.onDidReceiveMessage(
      async (message) => {
        if (message?.type === "panel.tabChanged" && typeof message.tab === "string") {
          activeTab = message.tab;
          await context.workspaceState.update(PANEL_TAB_STATE_KEY, activeTab);
          return;
        }
        if (message?.type === "panel.action") {
          await handlers.onAction?.(message);
        }
      },
      null,
      context.subscriptions
    );

    render(lastState);
    return panelInstance;
  }

  return {
    reveal(state) {
      if (state) {
        lastState = state;
      }
      getOrCreatePanel();
      render(lastState);
    },
    render,
    dispose() {
      panelInstance?.dispose();
      panelInstance = null;
    },
    getLastRenderedHtml() {
      return lastRenderedHtml;
    },
  };
}

module.exports = {
  createPanelManager,
};
