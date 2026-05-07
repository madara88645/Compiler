function createHistoryEntry({ sourceText, scope, normalized, documentUri = "" }) {
  const savedAt = new Date().toISOString();
  return {
    id: `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    sourceText,
    scope,
    documentUri,
    savedAt,
    preview: compactPreview(sourceText),
    summary: {
      requestId: normalized.summary?.requestId || "unknown",
      processingMs: normalized.summary?.processingMs || 0,
      riskLevel: normalized.policy?.riskLevel || "low",
      domain: normalized.intent?.domain || "general",
    },
    intent: normalized.intent,
    policy: normalized.policy,
    artifacts: {
      system: normalized.prompts?.system || "",
      user: normalized.prompts?.user || "",
      plan: normalized.prompts?.plan || "",
      expanded: normalized.prompts?.expanded || "",
    },
    raw: normalized.raw || {},
  };
}

function pushHistoryEntry(entries, nextEntry, maxSize) {
  const safeEntries = Array.isArray(entries)
    ? entries.filter((entry) => entry && typeof entry.id === "string" && entry.id)
    : [];
  return [nextEntry, ...safeEntries.filter((entry) => entry.id !== nextEntry.id)].slice(0, Math.max(1, maxSize));
}

function sanitizeStoredEntries(entries) {
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries.filter((entry) => {
    return Boolean(
      entry &&
        typeof entry.id === "string" &&
        entry.id &&
        typeof entry.sourceText === "string" &&
        typeof entry.scope === "string" &&
        typeof entry.savedAt === "string" &&
        typeof entry.preview === "string" &&
        entry.summary &&
        typeof entry.summary.requestId === "string" &&
        typeof entry.summary.processingMs === "number" &&
        typeof entry.summary.riskLevel === "string" &&
        typeof entry.summary.domain === "string" &&
        entry.artifacts &&
        typeof entry.artifacts.system === "string" &&
        typeof entry.artifacts.user === "string" &&
        typeof entry.artifacts.plan === "string" &&
        typeof entry.artifacts.expanded === "string"
    );
  });
}

function compactPreview(text) {
  return text.replace(/\s+/g, " ").trim().slice(0, 96);
}

module.exports = {
  createHistoryEntry,
  pushHistoryEntry,
  sanitizeStoredEntries,
};
