import { STORAGE_KEYS, loadRuntimeConfig } from "./config.mjs";
import { buildPreviewEntry, mergePreviewHistory } from "./preview-history.mjs";

console.log("MyCompiler Background Worker Loaded");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type !== "OPTIMIZE_PROMPT") {
    return false;
  }

  handleOptimization(request, sender)
    .then(sendResponse)
    .catch((error) => {
      console.error("Optimization failed:", error);
      sendResponse({
        success: false,
        error: error instanceof Error ? error.message : "Optimization failed.",
      });
    });

  return true;
});

async function handleOptimization(request, sender) {
  const storage = await chrome.storage.local.get([STORAGE_KEYS.enabled]);
  if (storage[STORAGE_KEYS.enabled] === false) {
    return { success: false, error: "Extension is disabled." };
  }

  const runtimeConfig = await loadRuntimeConfig(chrome.storage.local);
  if (!runtimeConfig.ok) {
    return { success: false, error: runtimeConfig.error };
  }

  const text = typeof request.text === "string" ? request.text.trim() : "";
  if (!text) {
    return { success: false, error: "Prompt is empty." };
  }

  const response = await fetch(`${runtimeConfig.value.backendUrl}/compile/fast`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": runtimeConfig.value.apiKey,
    },
    body: JSON.stringify({
      text,
      v2: true,
    }),
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API Error ${response.status}: ${errText}`);
  }

  const data = await response.json();
  const result = data.expanded_prompt_v2 || data.expanded_prompt || data.system_prompt;
  await persistPreviewHistory({
    originalText: text,
    optimizedText: result,
    sourceUrl: sender?.tab?.url || sender?.url || "",
  });

  return { success: true, data: result };
}

async function persistPreviewHistory({ originalText, optimizedText, sourceUrl }) {
  const stored = await chrome.storage.local.get([STORAGE_KEYS.previewHistory]);
  const entry = buildPreviewEntry({ originalText, optimizedText, sourceUrl });
  const history = mergePreviewHistory(stored[STORAGE_KEYS.previewHistory], entry);
  await chrome.storage.local.set({ [STORAGE_KEYS.previewHistory]: history });
}
