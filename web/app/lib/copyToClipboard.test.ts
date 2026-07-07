import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { toast } from "sonner";
import { copyToClipboard } from "./copyToClipboard";

describe("copyToClipboard", () => {
  beforeEach(() => {
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves true and shows a success toast when writeText succeeds", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    const result = await copyToClipboard("hello world");

    expect(result).toBe(true);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("hello world");
    expect(toast.success).toHaveBeenCalledWith("Copied to clipboard");
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("resolves false and shows a failure toast when writeText rejects (e.g. unfocused tab)", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });

    const result = await copyToClipboard("hello world");

    expect(result).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("Copy failed — select the text manually");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("resolves false when navigator.clipboard is unavailable (non-secure context)", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });

    const result = await copyToClipboard("hello world");

    expect(result).toBe(false);
    expect(toast.error).toHaveBeenCalledWith("Copy failed — select the text manually");
  });

  it("supports custom success/failure messages", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    await copyToClipboard("md", { successMessage: "Copied report as Markdown" });

    expect(toast.success).toHaveBeenCalledWith("Copied report as Markdown");
  });
});
