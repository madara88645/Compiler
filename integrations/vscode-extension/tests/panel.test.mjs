import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { renderPanelHtml } = require("../src/panel.js");

test("renderPanelHtml includes artifact actions and preserves active tab state", () => {
  const html = renderPanelHtml(
    {
      intent: { domain: "engineering", persona: "assistant", intents: ["code"] },
      policy: {
        riskLevel: "low",
        riskDomains: [],
        allowedTools: [],
        forbiddenTools: [],
        sanitizationRules: [],
        dataSensitivity: "public",
        executionMode: "advice_only",
      },
      prompts: {
        system: "system prompt",
        user: "user prompt",
        plan: "plan prompt",
        expanded: "expanded prompt",
      },
      summary: { requestId: "req_1", processingMs: 12 },
      raw: {},
    },
    { activeTab: "prompts" }
  );

  assert.match(html, /data-action="copy-artifact"/);
  assert.match(html, /data-action="insert-artifact"/);
  assert.match(html, /data-action="save-favorite"/);
  assert.match(html, /data-tab="prompts"/);
  assert.match(html, /PromptC Panel/);
});
