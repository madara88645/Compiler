export function formatRelativeTime(timestamp, now = Date.now()) {
  const diffMs = now - timestamp;
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

export function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function getConfigStatusView(result, justSaved = false) {
  if (result.ok) {
    return {
      text: justSaved ? "Saved" : "Configured",
      className: "status-enabled",
    };
  }

  return {
    text: justSaved ? "Check fields" : "Missing config",
    className: justSaved ? "status-warning" : "status-disabled",
  };
}

export function renderPreviewHistoryItems(previewHistory, activePreviewId, now = Date.now()) {
  return previewHistory
    .map((historyEntry) => {
      const snippet = historyEntry.optimizedText.replace(/\s+/g, " ").trim().slice(0, 64);
      const activeClass = historyEntry.id === activePreviewId ? " history-item-active" : "";
      return `
          <button class="history-item${activeClass}" type="button" data-preview-id="${historyEntry.id}">
            <div class="history-item-top">
              <span class="history-item-title">${escapeHtml(historyEntry.siteLabel)}</span>
              <span class="history-item-time">${formatRelativeTime(historyEntry.createdAt, now)}</span>
            </div>
            <div class="history-item-snippet">${escapeHtml(snippet)}${historyEntry.optimizedText.length > 64 ? "..." : ""}</div>
          </button>
        `;
    })
    .join("");
}
