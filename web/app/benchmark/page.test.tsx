import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BenchmarkPage from "./page";
import { apiJson } from "@/config";

vi.mock("@/config", async () => {
  const actual = await vi.importActual<typeof import("@/config")>("@/config");
  return {
    ...actual,
    apiJson: vi.fn(),
  };
});

vi.mock("../lib/showError", () => ({
  showError: vi.fn(),
}));

vi.mock("../components/InfoButton", () => ({
  default: ({ title }: { title: string }) => <button type="button">{title}</button>,
}));

vi.mock("../components/DiffViewer", () => ({
  default: ({ oldText, newText }: { oldText: string; newText: string }) => (
    <div data-testid="diff-viewer">
      <div>{oldText}</div>
      <div>{newText}</div>
    </div>
  ),
}));

vi.mock("recharts", () => ({
  Legend: () => null,
  PolarAngleAxis: () => null,
  PolarGrid: () => null,
  PolarRadiusAxis: () => null,
  Radar: () => null,
  RadarChart: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

const apiJsonMock = vi.mocked(apiJson);

describe("Benchmark page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    apiJsonMock.mockReset();
  });

  it("lets the user switch into mock mode and shows the demo banner", async () => {
    vi.useFakeTimers();

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "mock" },
    });

    expect(
      screen.getByText(
        "No model is called. Numbers below are randomized for UI preview only — pick a real model to run an actual benchmark.",
      ),
    ).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain how a prompt compiler helps." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });

    expect(apiJsonMock).not.toHaveBeenCalled();
    expect(screen.getByText("Demo data — not a real benchmark.")).toBeTruthy();
    expect(screen.getByText("Demo result (Mock Engine — fake scores)")).toBeTruthy();
  });

  it("submits the default OpenRouter model and prompt to the benchmark route", async () => {
    apiJsonMock.mockResolvedValueOnce({
      raw_output: "Raw answer",
      compiled_output: "Compiled answer",
      metrics: {
        safety: { raw: 6, compiled: 9 },
        clarity: { raw: 5, compiled: 9 },
        conciseness: { raw: 5, compiled: 8 },
      },
      processing_ms: 4321,
      winner: "compiled",
      improvement_score: 35,
    });

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "  Write a safer onboarding checklist.  " },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    await waitFor(() => expect(apiJsonMock).toHaveBeenCalledTimes(1));

    const [path, options] = apiJsonMock.mock.calls[0];
    expect(path).toBe("/benchmark/run");
    expect(JSON.parse(options.body)).toEqual({
      text: "Write a safer onboarding checklist.",
      model: "openai/gpt-oss-20b",
    });

    expect(await screen.findByText("Benchmark complete (4321ms)")).toBeTruthy();
    expect(screen.getByText("COMPILED PROMPT")).toBeTruthy();
  });

  it("offers a mock-engine fallback when the real-model request fails for auth reasons", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("401 unauthorized"));

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain rate limiting." },
    });
    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "openai/gpt-oss-120b" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    expect(await screen.findByText("Cloud Benchmark Unavailable")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Switch to Mock Engine (Demo Trial)" }));

    expect(screen.getByText("Ready")).toBeTruthy();
    expect(screen.queryByText("Cloud Benchmark Unavailable")).toBeNull();
    expect((screen.getByLabelText("Model") as HTMLSelectElement).value).toBe("mock");
  });

  it("ends loading and shows a visible error when the benchmark request fails", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("Benchmark model request failed"));

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain rate limiting." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    expect(await screen.findByText("Benchmark failed")).toBeTruthy();
    expect(screen.getByText("Benchmark Issue")).toBeTruthy();

    // Loading state cleared: button is no longer "Running..." and is re-enabled.
    expect(screen.queryByText("Running...")).toBeNull();
    const runButton = screen.getByRole("button", { name: /Run Benchmark/i }) as HTMLButtonElement;
    expect(runButton.disabled).toBe(false);
  });

  it("does not stay stuck on Running when the request never resolves", async () => {
    vi.useFakeTimers();
    // Simulate a request that hangs forever (never resolves or rejects).
    apiJsonMock.mockReturnValueOnce(new Promise<never>(() => {}));

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain rate limiting." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    // While in flight the button shows the running state.
    expect(screen.getByText("Running...")).toBeTruthy();

    // Advance past the client-side benchmark timeout (default 60s).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(screen.getByText("Benchmark failed")).toBeTruthy();
    expect(screen.getByText("Benchmark Issue")).toBeTruthy();
    expect(screen.getAllByText(/Benchmark timed out/i).length).toBeGreaterThan(0);

    // Loading state cleared: button reset and re-enabled, not stuck on "Running...".
    expect(screen.queryByText("Running...")).toBeNull();
    const runButton = screen.getByRole("button", { name: /Run Benchmark/i }) as HTMLButtonElement;
    expect(runButton.disabled).toBe(false);
  });

  it("shows an error instead of crashing when the response is malformed", async () => {
    apiJsonMock.mockResolvedValueOnce({ unexpected: "shape" } as never);

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain rate limiting." },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    expect(await screen.findByText("Benchmark failed")).toBeTruthy();
    expect(screen.getByText("Benchmark Issue")).toBeTruthy();
    expect(screen.queryByText("Running...")).toBeNull();
  });

  it("recovers on retry after a failed run", async () => {
    apiJsonMock
      .mockRejectedValueOnce(new Error("Benchmark model request failed"))
      .mockResolvedValueOnce({
        raw_output: "Raw answer",
        compiled_output: "Compiled answer",
        metrics: {
          safety: { raw: 6, compiled: 9 },
          clarity: { raw: 5, compiled: 9 },
          conciseness: { raw: 5, compiled: 8 },
        },
        processing_ms: 4321,
        winner: "compiled",
        improvement_score: 35,
      });

    render(<BenchmarkPage />);

    fireEvent.change(screen.getByLabelText("Benchmark prompt input"), {
      target: { value: "Explain rate limiting." },
    });

    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);
    expect(await screen.findByText("Benchmark failed")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Run Benchmark/i }));
    expect(await screen.findByText("Benchmark complete (4321ms)")).toBeTruthy();
    expect(screen.getByText("COMPILED PROMPT")).toBeTruthy();
    expect(apiJsonMock).toHaveBeenCalledTimes(2);
  });
});
