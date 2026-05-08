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

function createTimeoutSignal(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error("PromptC request timed out.")), timeoutMs);
  return {
    signal: controller.signal,
    cancel: () => clearTimeout(timer),
  };
}

function readHeader(headers, name) {
  if (!headers) {
    return "";
  }
  if (typeof headers.get === "function") {
    return headers.get(name) || "";
  }
  if (typeof headers[name] === "string") {
    return headers[name];
  }
  if (typeof headers.get === "undefined" && typeof headers.entries === "function") {
    for (const [key, value] of headers.entries()) {
      if (String(key).toLowerCase() === name.toLowerCase()) {
        return value;
      }
    }
  }
  return "";
}

async function readErrorDetail(response) {
  const contentType = readHeader(response.headers, "content-type");
  if (contentType.includes("application/json") && typeof response.json === "function") {
    const payload = await response.json();
    return payload?.detail || JSON.stringify(payload);
  }
  if (typeof response.text === "function") {
    return response.text();
  }
  return "";
}

async function fetchCompileResult({
  baseUrl,
  text,
  conservativeMode,
  apiKey,
  timeoutMs = 30000,
  fetchImpl = fetch,
}) {
  const request = createTimeoutSignal(timeoutMs);
  try {
    const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/compile`, {
      method: "POST",
      headers: buildHeaders(apiKey),
      body: JSON.stringify(buildCompileRequest(text, conservativeMode)),
      signal: request.signal,
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      const suffix = detail ? `: ${detail}` : "";
      const error = new Error(`PromptC request failed with status ${response.status}${suffix}`);
      error.status = response.status;
      throw error;
    }

    return response.json();
  } finally {
    request.cancel();
  }
}

async function fetchHealth({ baseUrl, timeoutMs = 3000, fetchImpl = fetch }) {
  const request = createTimeoutSignal(timeoutMs);

  try {
    const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/health`, {
      method: "GET",
      signal: request.signal,
    });

    if (!response.ok) {
      const error = new Error(`PromptC health check failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const payload = await response.json();
    return { ok: true, status: payload?.status || "unknown" };
  } finally {
    request.cancel();
  }
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
    summary: {
      requestId: payload.request_id || "unknown",
      processingMs: payload.processing_ms || 0,
      riskLevel: policy.risk_level || "low",
      domain: ir.domain || "general",
    },
    raw: payload,
  };
}

module.exports = {
  buildCompileRequest,
  buildHeaders,
  fetchHealth,
  fetchCompileResult,
  normalizeCompileResponse,
};
