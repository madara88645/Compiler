import { afterEach, describe, expect, test, vi } from "vitest";
import {
  ApiError,
  TimeoutError,
  describeApiError,
  describeRequestError,
  withTimeout,
} from "./config";

describe("describeApiError", () => {
  test("403 with no payload detail returns the access-required message", () => {
    expect(describeApiError(403, null)).toBe(
      "This action requires a valid API key or additional backend access.",
    );
  });

  test("403 with a string payload uses the payload as the detail", () => {
    expect(describeApiError(403, "Missing bearer token")).toBe("Missing bearer token");
  });

  test("403 with an object payload uses payload.detail", () => {
    expect(describeApiError(403, { detail: "No scope for this workspace" })).toBe(
      "No scope for this workspace",
    );
  });

  test("429 with no payload detail returns the rate-limit message", () => {
    expect(describeApiError(429, undefined)).toBe(
      "Rate limit exceeded. Please retry in a moment.",
    );
  });

  test("429 with a payload detail uses the payload", () => {
    expect(describeApiError(429, { detail: "Too many requests, slow down" })).toBe(
      "Too many requests, slow down",
    );
  });

  test("5xx with no payload detail returns the internal-error message", () => {
    expect(describeApiError(500, {})).toBe("The backend hit an internal error.");
    expect(describeApiError(503, {})).toBe("The backend hit an internal error.");
  });

  test("5xx with a payload detail uses the payload", () => {
    expect(describeApiError(502, { detail: "Upstream provider unreachable" })).toBe(
      "Upstream provider unreachable",
    );
  });

  test("other status codes fall back to a generic API Error message", () => {
    expect(describeApiError(404, null)).toBe("API Error: 404");
  });

  test("whitespace-only string payload is treated as absent", () => {
    expect(describeApiError(403, "   ")).toBe(
      "This action requires a valid API key or additional backend access.",
    );
  });

  test("payload.detail that is not a string is ignored", () => {
    expect(describeApiError(500, { detail: 12345 })).toBe(
      "The backend hit an internal error.",
    );
  });
});

describe("describeRequestError", () => {
  test("ApiError passes through its own detail message", () => {
    const error = new ApiError(403, "Forbidden by policy", { detail: "Forbidden by policy" });
    expect(describeRequestError(error)).toBe("Forbidden by policy");
  });

  test("TimeoutError uses the default timeout copy", () => {
    expect(describeRequestError(new TimeoutError())).toBe(
      "The backend took too long to respond.",
    );
  });

  test("TimeoutError uses custom timeout copy when provided", () => {
    expect(describeRequestError(new TimeoutError(), { timeout: "Custom timeout copy" })).toBe(
      "Custom timeout copy",
    );
  });

  test("AbortError (by name) is treated like a timeout", () => {
    const abortError = new Error("The operation was aborted");
    abortError.name = "AbortError";
    expect(describeRequestError(abortError)).toBe("The backend took too long to respond.");
  });

  test("network-flavored error messages use custom network copy", () => {
    expect(
      describeRequestError(new Error("Failed to fetch"), { network: "Custom network copy" }),
    ).toBe("Custom network copy");
    expect(describeRequestError(new TypeError("NetworkError when attempting to fetch"))).toBe(
      "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
    );
    expect(describeRequestError(new Error("Load failed"))).toBe(
      "The service is temporarily unavailable or still waking up. Please retry in a few seconds.",
    );
  });

  test("other Error instances surface their own message", () => {
    expect(describeRequestError(new Error("Something specific broke"))).toBe(
      "Something specific broke",
    );
  });

  test("non-Error values fall back to the default connection-failed copy", () => {
    expect(describeRequestError("not an error object")).toBe("Connection failed.");
  });

  test("non-Error values use custom fallback copy when provided", () => {
    expect(describeRequestError(null, { fallback: "Custom fallback copy" })).toBe(
      "Custom fallback copy",
    );
  });
});

describe("withTimeout", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  test("resolves with the original value when the promise settles before the timeout", async () => {
    const result = await withTimeout(Promise.resolve("done"), 1000);
    expect(result).toBe("done");
  });

  test("rejects with the original error when the promise rejects before the timeout", async () => {
    await expect(withTimeout(Promise.reject(new Error("boom")), 1000)).rejects.toThrow("boom");
  });

  test("rejects with a TimeoutError once the timeout elapses", async () => {
    vi.useFakeTimers();
    const neverSettles = new Promise<string>(() => {});

    const pending = withTimeout(neverSettles, 5000);
    const assertion = expect(pending).rejects.toBeInstanceOf(TimeoutError);
    await vi.advanceTimersByTimeAsync(5000);

    await assertion;
  });

  test("calls onTimeout when the timeout elapses", async () => {
    vi.useFakeTimers();
    const neverSettles = new Promise<string>(() => {});
    const onTimeout = vi.fn();

    const pending = withTimeout(neverSettles, 1000, onTimeout);
    pending.catch(() => {});
    await vi.advanceTimersByTimeAsync(1000);

    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  test("does not call onTimeout when the promise settles before the timeout", async () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();

    const pending = withTimeout(Promise.resolve("fast"), 5000, onTimeout);
    await vi.advanceTimersByTimeAsync(0);
    await pending;
    await vi.advanceTimersByTimeAsync(5000);

    expect(onTimeout).not.toHaveBeenCalled();
  });
});
