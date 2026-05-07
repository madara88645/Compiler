const { ARTIFACT_TYPES } = require("./constants");

function createEmptyPanelState() {
  return {
    intent: { domain: "general", persona: "assistant", intents: [] },
    policy: {
      riskLevel: "low",
      riskDomains: [],
      allowedTools: [],
      forbiddenTools: [],
      sanitizationRules: [],
      dataSensitivity: "public",
      executionMode: "advice_only",
    },
    prompts: { system: "", user: "", plan: "", expanded: "" },
    summary: {
      requestId: "not-run-yet",
      processingMs: 0,
      riskLevel: "low",
      domain: "general",
    },
    raw: {},
  };
}

function historyEntryToPanelState(entry) {
  if (!entry) {
    return createEmptyPanelState();
  }

  return {
    intent: entry.intent || createEmptyPanelState().intent,
    policy: entry.policy || createEmptyPanelState().policy,
    prompts: {
      system: entry.artifacts?.system || "",
      user: entry.artifacts?.user || "",
      plan: entry.artifacts?.plan || "",
      expanded: entry.artifacts?.expanded || "",
    },
    summary: entry.summary || createEmptyPanelState().summary,
    raw: entry.raw || {},
  };
}

function titleCaseArtifact(type) {
  if (!type) {
    return "Artifact";
  }
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function getArtifactOptions() {
  return ARTIFACT_TYPES.map((type) => ({
    label: titleCaseArtifact(type),
    description: `${titleCaseArtifact(type)} artifact`,
    type,
  }));
}

module.exports = {
  createEmptyPanelState,
  historyEntryToPanelState,
  titleCaseArtifact,
  getArtifactOptions,
};
