function createFavoriteEntry(entry, artifactType) {
  const content = entry?.artifacts?.[artifactType] || "";
  return {
    id: `${artifactType}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    artifactType,
    label: `${artifactType}: ${entry?.summary?.requestId || "latest"}`,
    content,
    savedAt: new Date().toISOString(),
    requestId: entry?.summary?.requestId || "unknown",
    domain: entry?.summary?.domain || "general",
    riskLevel: entry?.summary?.riskLevel || "low",
  };
}

function pushFavoriteEntry(entries, nextEntry, maxSize = 50) {
  const prior = sanitizeStoredFavorites(entries).filter(
    (entry) => !(entry.artifactType === nextEntry.artifactType && entry.content === nextEntry.content)
  );
  return [nextEntry, ...prior].slice(0, Math.max(1, maxSize));
}

function sanitizeStoredFavorites(entries) {
  if (!Array.isArray(entries)) {
    return [];
  }

  return entries.filter((entry) => {
    return Boolean(
      entry &&
        typeof entry.id === "string" &&
        typeof entry.artifactType === "string" &&
        typeof entry.label === "string" &&
        typeof entry.content === "string" &&
        typeof entry.savedAt === "string" &&
        typeof entry.requestId === "string"
    );
  });
}

module.exports = {
  createFavoriteEntry,
  pushFavoriteEntry,
  sanitizeStoredFavorites,
};
