import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { toast } from "sonner";

import CopyButton from "./CopyButton";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

describe("CopyButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(toast.success).mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("copies the provided text, shows success feedback, and resets after the toast window", async () => {
    render(<CopyButton text="Compiled prompt output" />);

    fireEvent.click(screen.getByRole("button", { name: "Copy to Clipboard" }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Compiled prompt output");
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith("Copied to clipboard");
    expect(screen.getByRole("button", { name: "Copied" }).getAttribute("title")).toBe("Copied!");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByRole("button", { name: "Copy to Clipboard" }).getAttribute("title")).toBe(
      "Copy to Clipboard",
    );
  });

  it("supports the gray variant while preserving a custom accessibility label", () => {
    render(<CopyButton text={'{"ok":true}'} label="Copy JSON output" variant="gray" />);

    const button = screen.getByRole("button", { name: "Copy JSON output" });

    expect(button.getAttribute("title")).toBe("Copy JSON output");
    expect(button.className).toContain("bg-zinc-700");
    expect(button.className).toContain("focus-visible:ring-zinc-500");
  });
});
