import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BenchmarkPage from "./page";
import { apiJson } from "@/config";

vi.mock("@/config", () => ({
  apiJson: vi.fn(),
}));

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

  it("shows a mock-only helper message and demo banner for the default engine", async () => {
    vi.useFakeTimers();

    render(<BenchmarkPage />);

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

  it("submits the selected real model and prompt to the benchmark route", async () => {
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
    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "openai/gpt-oss-20b" },
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
      target: { value: "llama-3.1-8b-instant" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Run Benchmark/i })[0]);

    expect(await screen.findByText("API Key Required")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Switch to Mock Engine (Demo Trial)" }));

    expect(screen.getByText("Ready")).toBeTruthy();
    expect(screen.queryByText("API Key Required")).toBeNull();
    expect((screen.getByLabelText("Model") as HTMLSelectElement).value).toBe("mock");
  });
});
