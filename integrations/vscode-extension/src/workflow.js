function buildDocsUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, "")}/docs`;
}

async function ensureHealthyBackend({ baseUrl, timeoutMs, fetchHealth }) {
  try {
    const payload = await fetchHealth({ baseUrl, timeoutMs });
    return {
      ok: payload?.status === "ok",
      status: payload?.status || "unknown",
    };
  } catch (error) {
    return {
      ok: false,
      kind: "connection",
      message: error?.message || "PromptC backend is unavailable.",
      docsUrl: buildDocsUrl(baseUrl),
    };
  }
}

async function requestCompileWithAuthRetry({
  initialApiKey,
  promptForApiKey,
  storeApiKey,
  compile,
}) {
  try {
    return await compile({ apiKey: initialApiKey || null });
  } catch (error) {
    if (error?.status !== 401 && error?.status !== 403) {
      throw error;
    }

    const apiKey = await promptForApiKey();
    if (!apiKey) {
      throw new Error("PromptC request requires an API key.");
    }

    await storeApiKey(apiKey);
    return compile({ apiKey });
  }
}

module.exports = {
  buildDocsUrl,
  ensureHealthyBackend,
  requestCompileWithAuthRetry,
};
