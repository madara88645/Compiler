const vscode = require("vscode");
const {
  DEFAULT_API_BASE_URL,
  DEFAULT_AUTO_OPEN_PANEL,
  DEFAULT_HISTORY_SIZE,
  DEFAULT_TIMEOUT_MS,
} = require("./constants");

function getExtensionConfig() {
  const config = vscode.workspace.getConfiguration("promptc");
  return {
    apiBaseUrl: config.get("apiBaseUrl", DEFAULT_API_BASE_URL),
    conservativeMode: config.get("conservativeMode", true),
    requestTimeoutMs: config.get("requestTimeoutMs", DEFAULT_TIMEOUT_MS),
    autoOpenPanel: config.get("autoOpenPanel", DEFAULT_AUTO_OPEN_PANEL),
    historySize: config.get("historySize", DEFAULT_HISTORY_SIZE),
  };
}

module.exports = {
  getExtensionConfig,
};
