import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { renderPanelHtml, escapeHtml } = require("../src/panel.js");

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

test("escapeHtml escapes quotes and nullish values used by the panel renderer", () => {
  assert.equal(
    escapeHtml(`Tom & "Jerry" <tag> 'quote'`),
    "Tom &amp; &quot;Jerry&quot; &lt;tag&gt; &#039;quote&#039;",
  );
  assert.equal(escapeHtml(undefined), "");
  assert.equal(escapeHtml(null), "");
});

test("renderPanelHtml escapes dangerous content in rendered sections", () => {
  const html = renderPanelHtml({
    intent: {
      domain: `<img src=x onerror=alert("boom")>`,
      persona: "assistant",
      intents: [`</li><script>alert("intent")</script>`],
    },
    policy: {
      riskLevel: "high",
      riskDomains: [`</div><script>alert("risk")</script>`],
      allowedTools: [],
      forbiddenTools: [],
      sanitizationRules: [],
      dataSensitivity: "public",
      executionMode: "advice_only",
    },
    prompts: {
      system: `<script>alert("system")</script>`,
      user: "safe",
      plan: "safe",
      expanded: "safe",
    },
    summary: { requestId: "req_2", processingMs: 42 },
    raw: {},
  });

  assert.match(html, /&lt;img src=x onerror=alert\(&quot;boom&quot;\)&gt;/);
  assert.match(html, /&lt;\/li&gt;&lt;script&gt;alert\(&quot;intent&quot;\)&lt;\/script&gt;/);
  assert.match(html, /&lt;script&gt;alert\(&quot;system&quot;\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<img src=x onerror=alert\("boom"\)>/);
  assert.doesNotMatch(html, /<script>alert\("system"\)<\/script>/);
});
