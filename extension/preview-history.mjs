export const PREVIEW_HISTORY_LIMIT = 3;

export function resolveSiteLabel(sourceUrl) {
  if (typeof sourceUrl !== "string" || !sourceUrl.trim()) {
    return "Unknown";
  }

  try {
    const url = new URL(sourceUrl);
    const host = url.hostname.toLowerCase();

    if (host.includes("chatgpt.com")) {
      return "ChatGPT";
    }

    if (host.includes("claude.ai")) {
      return "Claude";
    }

    if (host.includes("gemini.google.com")) {
      return "Gemini";
    }

    return url.hostname;
  } catch {
    return "Unknown";
  }
}

export function buildPreviewEntry({ originalText, optimizedText, sourceUrl, now = Date.now() }) {
  return {
    id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
    originalText,
    optimizedText,
    siteLabel: resolveSiteLabel(sourceUrl),
    createdAt: now,
  };
}

export function mergePreviewHistory(existingEntries, nextEntry, limit = PREVIEW_HISTORY_LIMIT) {
  const safeEntries = Array.isArray(existingEntries) ? existingEntries : [];
  return [nextEntry, ...safeEntries].slice(0, limit);
}
