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

function renderPanelHtml(state) {
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
    raw: {},
  };

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
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
    </style>
  </head>
  <body>
    <div class="tabs">
      <button class="tab-button active" data-tab="intent">Intent</button>
      <button class="tab-button" data-tab="policy">Policy</button>
      <button class="tab-button" data-tab="prompts">Prompts</button>
      <button class="tab-button" data-tab="raw">Raw JSON</button>
    </div>

    <section id="intent" class="tab active">
      <div class="card">
        <h2>Intent</h2>
        <div class="meta">
          <div><strong>Domain</strong><div>${escapeHtml(normalized.intent.domain)}</div></div>
          <div><strong>Persona</strong><div>${escapeHtml(normalized.intent.persona)}</div></div>
        </div>
        <h3>Detected Intents</h3>
        ${renderList(normalized.intent.intents, "No special intent flags detected.")}
      </div>
    </section>

    <section id="policy" class="tab">
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

    <section id="prompts" class="tab">
      <div class="card"><h3>System</h3><pre>${escapeHtml(normalized.prompts.system)}</pre></div>
      <div class="card"><h3>User</h3><pre>${escapeHtml(normalized.prompts.user)}</pre></div>
      <div class="card"><h3>Plan</h3><pre>${escapeHtml(normalized.prompts.plan)}</pre></div>
      <div class="card"><h3>Expanded</h3><pre>${escapeHtml(normalized.prompts.expanded)}</pre></div>
    </section>

    <section id="raw" class="tab">
      <pre>${escapeHtml(JSON.stringify(normalized.raw, null, 2))}</pre>
    </section>

    <script>
      const buttons = Array.from(document.querySelectorAll(".tab-button"));
      const tabs = Array.from(document.querySelectorAll(".tab"));
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          buttons.forEach((item) => item.classList.remove("active"));
          tabs.forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          document.getElementById(button.dataset.tab).classList.add("active");
        });
      });
    </script>
  </body>
</html>`;
}

module.exports = {
  renderPanelHtml,
};
