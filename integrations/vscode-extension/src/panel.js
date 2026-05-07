function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderList(items, emptyLabel) {
  if (!items || items.length === 0) {
    return `<div class="empty">${escapeHtml(emptyLabel)}</div>`;
  }

  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderArtifactCard(title, type, value) {
  return `<div class="card">
    <div class="artifact-header">
      <h3>${escapeHtml(title)}</h3>
      <div class="artifact-actions">
        <button data-action="copy-artifact" data-artifact="${escapeHtml(type)}">Copy</button>
        <button data-action="insert-artifact" data-artifact="${escapeHtml(type)}">Insert</button>
        <button data-action="save-favorite" data-artifact="${escapeHtml(type)}">Favorite</button>
      </div>
    </div>
    <pre>${escapeHtml(value)}</pre>
  </div>`;
}

function renderPanelHtml(state, options = {}) {
  const normalized = state || {
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
    summary: { requestId: "not-run-yet", processingMs: 0 },
    raw: {},
  };
  const activeTab = options.activeTab || "intent";

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
      h1 { margin-top: 0; margin-bottom: 16px; }
      .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
      .tab-button { border: 1px solid var(--vscode-panel-border); background: transparent; color: inherit; padding: 8px 12px; cursor: pointer; border-radius: 8px; }
      .tab-button.active { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
      .tab { display: none; }
      .tab.active { display: block; }
      .card { border: 1px solid var(--vscode-panel-border); border-radius: 12px; padding: 12px; margin-bottom: 12px; }
      h2, h3 { margin: 0 0 8px; }
      pre { white-space: pre-wrap; overflow-wrap: anywhere; border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 12px; }
      ul { padding-left: 18px; }
      .empty { opacity: 0.7; }
      .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
      .artifact-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
      .artifact-actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .artifact-actions button { border: 1px solid var(--vscode-panel-border); background: transparent; color: inherit; padding: 6px 10px; border-radius: 8px; cursor: pointer; }
    </style>
  </head>
  <body>
    <h1>PromptC Panel</h1>
    <div class="tabs">
      <button class="tab-button ${activeTab === "intent" ? "active" : ""}" data-tab="intent">Intent</button>
      <button class="tab-button ${activeTab === "policy" ? "active" : ""}" data-tab="policy">Policy</button>
      <button class="tab-button ${activeTab === "prompts" ? "active" : ""}" data-tab="prompts">Prompts</button>
      <button class="tab-button ${activeTab === "raw" ? "active" : ""}" data-tab="raw">Raw JSON</button>
    </div>

    <section id="intent" class="tab ${activeTab === "intent" ? "active" : ""}">
      <div class="card">
        <h2>Intent</h2>
        <div class="meta">
          <div><strong>Domain</strong><div>${escapeHtml(normalized.intent.domain)}</div></div>
          <div><strong>Persona</strong><div>${escapeHtml(normalized.intent.persona)}</div></div>
          <div><strong>Request ID</strong><div>${escapeHtml(normalized.summary.requestId)}</div></div>
          <div><strong>Latency</strong><div>${escapeHtml(normalized.summary.processingMs)} ms</div></div>
        </div>
        <h3>Detected Intents</h3>
        ${renderList(normalized.intent.intents, "No special intent flags detected.")}
      </div>
    </section>

    <section id="policy" class="tab ${activeTab === "policy" ? "active" : ""}">
      <div class="card">
        <h2>Policy</h2>
        <div class="meta">
          <div><strong>Risk Level</strong><div>${escapeHtml(normalized.policy.riskLevel)}</div></div>
          <div><strong>Execution Mode</strong><div>${escapeHtml(normalized.policy.executionMode)}</div></div>
          <div><strong>Data Sensitivity</strong><div>${escapeHtml(normalized.policy.dataSensitivity)}</div></div>
        </div>
      </div>
      <div class="card">
        <h3>Risk Domains</h3>
        ${renderList(normalized.policy.riskDomains, "No risk domains inferred.")}
      </div>
      <div class="card">
        <h3>Allowed Tools</h3>
        ${renderList(normalized.policy.allowedTools, "No tool allowlist inferred.")}
      </div>
      <div class="card">
        <h3>Forbidden Tools</h3>
        ${renderList(normalized.policy.forbiddenTools, "No forbidden tools inferred.")}
      </div>
      <div class="card">
        <h3>Sanitization Rules</h3>
        ${renderList(normalized.policy.sanitizationRules, "No extra sanitization rules inferred.")}
      </div>
    </section>

    <section id="prompts" class="tab ${activeTab === "prompts" ? "active" : ""}">
      ${renderArtifactCard("System", "system", normalized.prompts.system)}
      ${renderArtifactCard("User", "user", normalized.prompts.user)}
      ${renderArtifactCard("Plan", "plan", normalized.prompts.plan)}
      ${renderArtifactCard("Expanded", "expanded", normalized.prompts.expanded)}
    </section>

    <section id="raw" class="tab ${activeTab === "raw" ? "active" : ""}">
      <pre>${escapeHtml(JSON.stringify(normalized.raw, null, 2))}</pre>
    </section>

    <script>
      const vscode = typeof acquireVsCodeApi === "function" ? acquireVsCodeApi() : null;
      const buttons = Array.from(document.querySelectorAll(".tab-button"));
      const tabs = Array.from(document.querySelectorAll(".tab"));
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          buttons.forEach((item) => item.classList.remove("active"));
          tabs.forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          document.getElementById(button.dataset.tab).classList.add("active");
          if (vscode) {
            vscode.postMessage({ type: "panel.tabChanged", tab: button.dataset.tab });
          }
        });
      });

      Array.from(document.querySelectorAll("[data-action]")).forEach((button) => {
        button.addEventListener("click", () => {
          if (!vscode) {
            return;
          }
          vscode.postMessage({
            type: "panel.action",
            action: button.dataset.action,
            artifact: button.dataset.artifact,
          });
        });
      });
    </script>
  </body>
</html>`;
}

module.exports = {
  renderPanelHtml,
};
