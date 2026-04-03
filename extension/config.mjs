export const STORAGE_KEYS = {
  enabled: "enabled",
  conservativeMode: "promptc_conservative_mode",
  backendUrl: "promptc_backend_url",
  apiKey: "promptc_api_key",
  previewHistory: "promptc_preview_history",
};

const CONFIGURATION_ERROR =
  "Extension is not configured yet. Add your backend URL in the popup.";

export function normalizeBackendUrl(input) {
  if (typeof input !== "string") {
    return "";
  }

  const trimmed = input.trim();
  if (!trimmed) {
    return "";
  }

  const prefixed = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  try {
    const url = new URL(prefixed);
    const pathname = url.pathname.replace(/\/+$/, "");
    return `${url.origin}${pathname === "/" ? "" : pathname}`;
  } catch {
    return "";
  }
}

export function resolveRuntimeConfig(rawConfig = {}) {
  const backendUrl = normalizeBackendUrl(rawConfig.backendUrl);

  if (!backendUrl) {
    return { ok: false, error: CONFIGURATION_ERROR };
  }

  const apiKey =
    typeof rawConfig.apiKey === "string" ? rawConfig.apiKey.trim() : "";

  if (apiKey && backendUrl.startsWith("http://")) {
    try {
      const { hostname } = new URL(backendUrl);
      if (hostname !== "localhost" && hostname !== "127.0.0.1") {
        console.warn(
          "[PromptC] Security warning: API key is being sent over an unencrypted HTTP connection to a non-local host. Use HTTPS to protect your credentials."
        );
      }
    } catch {
      // malformed URL — normalizeBackendUrl already validated, so this is a no-op
    }
  }

  return {
    ok: true,
    value: {
      backendUrl,
      apiKey,
    },
  };
}

export async function loadRuntimeConfig(storageArea) {
  const stored = await storageArea.get([STORAGE_KEYS.backendUrl, STORAGE_KEYS.apiKey]);

  return resolveRuntimeConfig({
    backendUrl: stored[STORAGE_KEYS.backendUrl],
    apiKey: stored[STORAGE_KEYS.apiKey],
  });
}
