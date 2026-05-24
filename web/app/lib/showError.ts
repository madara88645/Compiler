import { toast } from "sonner";
import { ApiError, describeRequestError } from "../../config";

function summarizeForConsole(error: unknown): Record<string, unknown> {
  if (error instanceof ApiError) {
    const requestId =
      error.payload && typeof error.payload === "object"
        ? (error.payload as { request_id?: unknown }).request_id
        : undefined;
    return {
      kind: "ApiError",
      status: error.status,
      detail: error.detail,
      requestId,
      payload: error.payload,
    };
  }
  if (error instanceof Error) {
    return { kind: error.name || "Error", message: error.message };
  }
  return { kind: "unknown", value: error };
}

export function showError(error: unknown): void {
  const userMessage = describeRequestError(error);
  console.error("[showError]", userMessage, summarizeForConsole(error), error);
  toast.error(userMessage);
}
