import { describe, expect, it, vi } from "vitest";

import { withTimeout } from "./withTimeout";

describe("withTimeout", () => {
  it("resolves when the wrapped promise resolves in time", async () => {
    await expect(withTimeout(Promise.resolve("ok"), 1000, "too slow")).resolves.toBe("ok");
  });

  it("rejects with the provided message when the promise hangs", async () => {
    vi.useFakeTimers();

    try {
      const pending = withTimeout(new Promise(() => {}), 15000, "Repository analysis is taking too long.");

      vi.advanceTimersByTime(15000);

      await expect(pending).rejects.toThrow("Repository analysis is taking too long.");
    } finally {
      vi.useRealTimers();
    }
  });
});
