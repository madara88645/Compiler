import { STORAGE_KEYS, loadRuntimeConfig, normalizeBackendUrl } from "./config.mjs";
import {
  formatPreviewDelta,
  getActivePreviewEntry,
  getRestoreText,
} from "./popup-preview.mjs";

document.addEventListener("DOMContentLoaded", async () => {
  const enabledToggle = document.getElementById("enabledToggle");
  const statusLabel = document.getElementById("statusLabel");
  const playgroundButton = document.getElementById("openPlayground");
  const docsButton = document.getElementById("openDocs");
  const conservativeToggle = document.getElementById("pc-conservative-toggle");
  const backendUrlInput = document.getElementById("backendUrlInput");
  const apiKeyInput = document.getElementById("apiKeyInput");
  const saveConfigButton = document.getElementById("saveConfig");
  const configStatus = document.getElementById("configStatus");
  const restorePreviewButton = document.getElementById("restorePreview");
  const previewEmpty = document.getElementById("previewEmpty");
  const previewContent = document.getElementById("previewContent");
  const previewSite = document.getElementById("previewSite");
  const previewTime = document.getElementById("previewTime");
  const previewDelta = document.getElementById("previewDelta");
  const previewOriginal = document.getElementById("previewOriginal");
  const previewOptimized = document.getElementById("previewOptimized");
  const previewHistoryList = document.getElementById("previewHistoryList");

  const stored = await chrome.storage.local.get([
    STORAGE_KEYS.enabled,
    STORAGE_KEYS.conservativeMode,
    STORAGE_KEYS.backendUrl,
    STORAGE_KEYS.apiKey,
    STORAGE_KEYS.previewHistory,
  ]);
  let previewHistory = Array.isArray(stored[STORAGE_KEYS.previewHistory])
    ? stored[STORAGE_KEYS.previewHistory]
    : [];
  let activePreviewId = previewHistory[0]?.id ?? null;
  let restoreFeedbackTimeout = null;

  const isEnabled = stored[STORAGE_KEYS.enabled] !== false;
  enabledToggle.checked = isEnabled;
  updateStatus(isEnabled);

  const conservativeModeOn = stored[STORAGE_KEYS.conservativeMode] !== false;
  setConservativeUI(conservativeModeOn);

  backendUrlInput.value = stored[STORAGE_KEYS.backendUrl] || "";
  apiKeyInput.value = stored[STORAGE_KEYS.apiKey] || "";
  updateConfigStatus(await loadRuntimeConfig(chrome.storage.local));
  renderPreview();

  enabledToggle.addEventListener("change", async () => {
    const nextEnabled = enabledToggle.checked;
    await chrome.storage.local.set({ [STORAGE_KEYS.enabled]: nextEnabled });
    updateStatus(nextEnabled);
  });

  conservativeToggle?.addEventListener("click", async () => {
    const result = await chrome.storage.local.get([STORAGE_KEYS.conservativeMode]);
    const current = result[STORAGE_KEYS.conservativeMode] !== false;
    const next = !current;
    await chrome.storage.local.set({ [STORAGE_KEYS.conservativeMode]: next });
    setConservativeUI(next);
  });

  saveConfigButton?.addEventListener("click", async () => {
    const payload = {
      [STORAGE_KEYS.backendUrl]: normalizeBackendUrl(backendUrlInput.value) || backendUrlInput.value.trim(),
      [STORAGE_KEYS.apiKey]: apiKeyInput.value.trim(),
    };

    await chrome.storage.local.set(payload);
    updateConfigStatus(await loadRuntimeConfig(chrome.storage.local), true);
  });

  playgroundButton?.addEventListener("click", () => {
    chrome.tabs.create({ url: "http://localhost:3000" });
  });

  docsButton?.addEventListener("click", () => {
    chrome.tabs.create({ url: "https://github.com/madara88645/Compiler" });
  });

  restorePreviewButton?.addEventListener("click", async () => {
    const restoreText = getRestoreText(getActivePreviewEntry(previewHistory, activePreviewId));
    if (!restoreText) {
      return;
    }

    await navigator.clipboard.writeText(restoreText);
    setRestoreButtonState(true);
  });

  previewHistoryList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-preview-id]");
    if (!button) {
      return;
    }

    activePreviewId = button.getAttribute("data-preview-id");
    renderPreview();
  });

  function updateStatus(enabled) {
    statusLabel.textContent = enabled ? "Enabled" : "Disabled";
    statusLabel.classList.toggle("status-enabled", enabled);
    statusLabel.classList.toggle("status-disabled", !enabled);
  }

  function setConservativeUI(on) {
    if (!conservativeToggle) {
      return;
    }

    conservativeToggle.classList.toggle("pc-conservative-on", on);
    conservativeToggle.classList.toggle("pc-conservative-off", !on);
    conservativeToggle.setAttribute("aria-pressed", on ? "true" : "false");
    conservativeToggle.title = on
      ? "Conservative mode ON - keep prompts grounded and avoid hallucinations."
      : "Conservative mode OFF - use more aggressive optimization.";
  }

  function updateConfigStatus(result, justSaved = false) {
    if (!configStatus) {
      return;
    }

    configStatus.classList.remove("status-enabled", "status-disabled", "status-warning");

    if (result.ok) {
      configStatus.textContent = justSaved ? "Saved" : "Configured";
      configStatus.classList.add("status-enabled");
      return;
    }

    configStatus.textContent = justSaved ? "Check fields" : "Missing config";
    configStatus.classList.add(justSaved ? "status-warning" : "status-disabled");
  }

  function renderPreview() {
    const entry = getActivePreviewEntry(previewHistory, activePreviewId);

    if (!entry) {
      previewEmpty.hidden = false;
      previewContent.hidden = true;
      setRestoreButtonState(false);
      restorePreviewButton.disabled = true;
      return;
    }

    previewEmpty.hidden = true;
    previewContent.hidden = false;
    setRestoreButtonState(false);
    restorePreviewButton.disabled = false;

    previewSite.textContent = entry.siteLabel;
    previewTime.textContent = formatRelativeTime(entry.createdAt);
    previewDelta.textContent = formatPreviewDelta(entry);
    previewOriginal.textContent = entry.originalText;
    previewOptimized.textContent = entry.optimizedText;
    previewHistoryList.innerHTML = previewHistory
      .map((historyEntry) => {
        const snippet = historyEntry.optimizedText.replace(/\s+/g, " ").trim().slice(0, 64);
        const activeClass = historyEntry.id === entry.id ? " history-item-active" : "";
        return `
          <button class="history-item${activeClass}" type="button" data-preview-id="${historyEntry.id}">
            <div class="history-item-top">
              <span class="history-item-title">${escapeHtml(historyEntry.siteLabel)}</span>
              <span class="history-item-time">${formatRelativeTime(historyEntry.createdAt)}</span>
            </div>
            <div class="history-item-snippet">${escapeHtml(snippet)}${historyEntry.optimizedText.length > 64 ? "..." : ""}</div>
          </button>
        `;
      })
      .join("");
  }

  function formatRelativeTime(timestamp) {
    const diffMs = Date.now() - timestamp;
    const diffMinutes = Math.max(1, Math.round(diffMs / 60000));

    if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    }

    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    }

    const diffDays = Math.round(diffHours / 24);
    return `${diffDays}d ago`;
  }

  function escapeHtml(value) {
    return value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setRestoreButtonState(restored) {
    if (!restorePreviewButton) {
      return;
    }

    if (restoreFeedbackTimeout) {
      window.clearTimeout(restoreFeedbackTimeout);
      restoreFeedbackTimeout = null;
    }

    restorePreviewButton.textContent = restored ? "Restored" : "Restore";
    if (!restored) {
      return;
    }

    restoreFeedbackTimeout = window.setTimeout(() => {
      restorePreviewButton.textContent = "Restore";
      restoreFeedbackTimeout = null;
    }, 1400);
  }

  window.getPromptCompilerMode = function getPromptCompilerMode(callback) {
    chrome.storage.local.get([STORAGE_KEYS.conservativeMode], (result) => {
      const on = result[STORAGE_KEYS.conservativeMode] !== false;
      callback(on ? "conservative" : "default");
    });
  };
});
