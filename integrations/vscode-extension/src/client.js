function buildCompileRequest(text, conservativeMode) {
  return {
    text,
    diagnostics: true,
    v2: true,
    render_v2_prompts: true,
    mode: conservativeMode ? "conservative" : "default",
  };
}

function buildHeaders(apiKey) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (apiKey) {
    headers["x-api-key"] = apiKey;
  }

  return headers;
}

async function fetchCompileResult({ baseUrl, text, conservativeMode, apiKey, fetchImpl = fetch }) {
  const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/compile`, {
    method: "POST",
    headers: buildHeaders(apiKey),
    body: JSON.stringify(buildCompileRequest(text, conservativeMode)),
  });

  if (!response.ok) {
    const error = new Error(`PromptC request failed with status ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return response.json();
}

function normalizeCompileResponse(payload) {
  const ir = payload.ir_v2 || payload.ir || {};
  const policy = ir.policy || {};

  return {
    intent: {
      domain: ir.domain || "general",
      persona: ir.persona || "assistant",
      intents: ir.intents || [],
    },
    policy: {
      riskLevel: policy.risk_level || "low",
      riskDomains: policy.risk_domains || [],
      allowedTools: policy.allowed_tools || [],
      forbiddenTools: policy.forbidden_tools || [],
      sanitizationRules: policy.sanitization_rules || [],
      dataSensitivity: policy.data_sensitivity || "public",
      executionMode: policy.execution_mode || "advice_only",
    },
    prompts: {
      system: payload.system_prompt_v2 || payload.system_prompt || "",
      user: payload.user_prompt_v2 || payload.user_prompt || "",
      plan: payload.plan_v2 || payload.plan || "",
      expanded: payload.expanded_prompt_v2 || payload.expanded_prompt || "",
    },
    raw: payload,
  };
}

module.exports = {
  buildCompileRequest,
  buildHeaders,
  fetchCompileResult,
  normalizeCompileResponse,
};
