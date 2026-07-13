import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { toast } from "sonner";
import BenchmarkResults, { type BenchmarkData } from "./BenchmarkResults";

const CHECKMARK_SELECTOR = "polyline[points='20 6 9 17 4 12']";

const benchmarkData: BenchmarkData = {
  raw_output: "Raw benchmark output",
  compiled_output: "Compiled benchmark output",
  compiled_prompt: "Compiled prompt",
  winner: "compiled",
  improvement_score: 20,
  metrics: {
    raw_relevance: 6.5,
    compiled_relevance: 8.5,
    raw_clarity: 6.0,
    compiled_clarity: 8.0,
  },
  processing_ms: 120,
};

function deferredWrite() {
  let resolve: () => void;
  const promise = new Promise<void>((resolvePromise) => {
    resolve = resolvePromise;
  });

  return { promise, resolve: () => resolve() };
}

describe("BenchmarkResults", () => {
  beforeEach(() => {
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  it("shows the report copied state only after the clipboard write succeeds", async () => {
    const write = deferredWrite();
    const writeText = vi.fn().mockReturnValue(write.promise);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<BenchmarkResults data={benchmarkData} />);

    const button = screen.getByRole("button", { name: "Copy report" });
    fireEvent.click(button);

    expect(button).toHaveTextContent("Copy report");
    expect(toast.success).not.toHaveBeenCalled();

    await act(async () => {
      write.resolve();
      await write.promise;
    });

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("# Benchmark Report"));
    expect(toast.success).toHaveBeenCalledWith("Copied report as Markdown");
    expect(button).toHaveTextContent("Copied!");
  });

  it.each([
    ["raw output", "Copy raw output"],
    ["compiled output", "Copy compiled output"],
  ])("does not show a copied state when writing the %s is rejected", async (_label, buttonName) => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });

    render(<BenchmarkResults data={benchmarkData} />);

    const button = screen.getByRole("button", { name: buttonName });
    fireEvent.click(button);

    await act(async () => {
      await Promise.resolve();
    });

    expect(toast.error).toHaveBeenCalledWith("Copy failed — select the text manually");
    expect(toast.success).not.toHaveBeenCalled();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();
  });
});
