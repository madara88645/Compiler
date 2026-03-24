export function getActivePreviewEntry(previewHistory, activePreviewId) {
  const safeHistory = Array.isArray(previewHistory) ? previewHistory : [];
  return safeHistory.find((entry) => entry.id === activePreviewId) ?? safeHistory[0] ?? null;
}

export function getRestoreText(entry) {
  return typeof entry?.optimizedText === "string" ? entry.optimizedText : "";
}

export function formatPreviewDelta(entry) {
  const originalText = typeof entry?.originalText === "string" ? entry.originalText : "";
  const optimizedText = typeof entry?.optimizedText === "string" ? entry.optimizedText : "";
  const delta = optimizedText.length - originalText.length;

  return `${delta >= 0 ? "+" : ""}${delta} chars`;
}
