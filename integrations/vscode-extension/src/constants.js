const SECRET_KEY = "promptc.apiKey";
const HISTORY_STATE_KEY = "promptc.history";
const FAVORITES_STATE_KEY = "promptc.favorites";
const PANEL_TAB_STATE_KEY = "promptc.panelActiveTab";
const DEFAULT_HISTORY_SIZE = 20;
const DEFAULT_TIMEOUT_MS = 30000;
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8080";
const DEFAULT_AUTO_OPEN_PANEL = true;
const ARTIFACT_TYPES = ["system", "user", "plan", "expanded"];

module.exports = {
  SECRET_KEY,
  HISTORY_STATE_KEY,
  FAVORITES_STATE_KEY,
  PANEL_TAB_STATE_KEY,
  DEFAULT_HISTORY_SIZE,
  DEFAULT_TIMEOUT_MS,
  DEFAULT_API_BASE_URL,
  DEFAULT_AUTO_OPEN_PANEL,
  ARTIFACT_TYPES,
};
