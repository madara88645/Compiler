import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OptimizerPage from "../optimizer/page";
import { apiJson } from "@/config";

vi.mock("@/config", () => ({
  apiJson: vi.fn(),
}));

vi.mock("../components/InfoButton", () => ({
  default: ({ title }: { title: string }) => <button type="button">{title}</button>,
}));

const apiJsonMock = vi.mocked(apiJson);

describe("Optimizer page", () => {
  beforeEach(() => {
    apiJsonMock.mockReset();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("shows Groq cost estimates and a separate English suggestion", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "PDF'i ozetle. Junior gelistirici icin uygulama plani yaz.",
      before_chars: 96,
      after_chars: 62,
      before_tokens: 34,
      after_tokens: 21,
      saved_percent: 38.2,
      passes: 1,
      met_max_chars: true,
      met_max_tokens: true,
      met_budget: true,
      changed: true,
      provider: "groq",
      model: "llama-3.1-8b-instant",
      source_language: "tr",
      tokenizer_method: "tiktoken:o200k_base:estimated",
      estimated_input_cost_usd: 0.0000017,
      estimated_output_cost_usd: 0.0000011,
      estimated_savings_usd: 0.0000006,
      english_variant: "Summarize PDF. Write implementation plan for junior developer.",
      english_variant_tokens: 13,
      english_variant_cost_usd: 0.0000007,
      warnings: ["Translation can change nuance; review before using."],
      optimizer_call_usage: null,
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "Bu PDF'i ozetle ve junior gelistirici icin uygulama plani yaz." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    expect(await screen.findByText("Original estimate")).toBeTruthy();
    expect(screen.getByText("Optimized estimate")).toBeTruthy();
    expect(screen.getByText("Groq / llama-3.1-8b-instant")).toBeTruthy();
    expect(screen.getByText("TR")).toBeTruthy();
    expect(screen.getByText("38.2%")).toBeTruthy();
    expect(screen.getByDisplayValue("Summarize PDF. Write implementation plan for junior developer.")).toBeTruthy();
    expect(screen.getByText("Translation can change nuance; review before using.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy English variant" }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "Summarize PDF. Write implementation plan for junior developer.",
      );
    });
  });

  it("hides the English compact suggestion panel for an English source language", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "Write clear implementation plan.",
      before_chars: 40,
      after_chars: 32,
      before_tokens: 8,
      after_tokens: 5,
      saved_percent: 37.5,
      passes: 1,
      met_max_chars: true,
      met_max_tokens: true,
      met_budget: true,
      changed: true,
      provider: "groq",
      model: "llama-3.1-8b-instant",
      source_language: "en",
      tokenizer_method: "tiktoken:o200k_base:estimated",
      estimated_input_cost_usd: 0.0000004,
      estimated_output_cost_usd: 0.0000003,
      estimated_savings_usd: 0.0000001,
      english_variant: "",
      english_variant_tokens: 0,
      english_variant_cost_usd: 0,
      warnings: [],
      optimizer_call_usage: null,
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "Write a clear implementation plan." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    expect(await screen.findByText("EN")).toBeTruthy();
    expect(screen.queryByText("English compact suggestion")).toBeNull();
  });

  it("normalizes a legacy optimize response with missing cost fields", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "Write clear implementation plan.",
      before_chars: 40,
      after_chars: 32,
      before_tokens: 8,
      after_tokens: 5,
      saved_percent: 37.5,
      changed: true,
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "Write a clear implementation plan." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    expect(await screen.findByText("UNKNOWN")).toBeTruthy();
    expect(screen.queryByText("English compact suggestion")).toBeNull();
  });

  it("hides the English compact suggestion when the variant equals the main optimized text", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "Summarize PDF and write plan.",
      before_chars: 60,
      after_chars: 30,
      before_tokens: 18,
      after_tokens: 7,
      saved_percent: 61.1,
      changed: true,
      provider: "groq",
      model: "llama-3.1-8b-instant",
      source_language: "tr",
      tokenizer_method: "tiktoken:o200k_base:estimated",
      estimated_input_cost_usd: 0.0000018,
      estimated_output_cost_usd: 0.0000007,
      estimated_savings_usd: 0.0000011,
      english_variant: "Summarize PDF and write plan.",
      english_variant_tokens: 7,
      english_variant_cost_usd: 0.0000007,
      warnings: [],
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "Bu PDF'i ozetle ve plan yaz." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    expect(await screen.findByText("TR")).toBeTruthy();
    expect(screen.queryByText("English compact suggestion")).toBeNull();
  });

  it("renders warnings even when the English compact panel is hidden", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "Write clear plan.",
      before_chars: 40,
      after_chars: 18,
      before_tokens: 8,
      after_tokens: 4,
      saved_percent: 50,
      changed: true,
      provider: "groq",
      model: "llama-3.1-8b-instant",
      source_language: "en",
      tokenizer_method: "tiktoken:o200k_base:estimated",
      estimated_input_cost_usd: 0.0000004,
      estimated_output_cost_usd: 0.0000002,
      estimated_savings_usd: 0.0000002,
      english_variant: "",
      english_variant_tokens: 0,
      english_variant_cost_usd: 0,
      warnings: ["Optimized output uses more tokens than the input; consider keeping the original."],
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "Write a clear plan." },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    expect(
      await screen.findByText(
        "Optimized output uses more tokens than the input; consider keeping the original.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("English compact suggestion")).toBeNull();
  });

  it("formats sub-cent costs with scientific notation and keeps zero as $0", async () => {
    apiJsonMock.mockResolvedValueOnce({
      text: "ok",
      before_chars: 5,
      after_chars: 2,
      before_tokens: 2,
      after_tokens: 1,
      saved_percent: 50,
      changed: true,
      provider: "groq",
      model: "llama-3.1-8b-instant",
      source_language: "en",
      tokenizer_method: "tiktoken:o200k_base:estimated",
      estimated_input_cost_usd: 0.00000017,
      estimated_output_cost_usd: 0,
      estimated_savings_usd: 0.00000017,
      english_variant: "",
      english_variant_tokens: 0,
      english_variant_cost_usd: 0,
      warnings: [],
    });

    render(<OptimizerPage />);

    fireEvent.change(screen.getByLabelText("Original Prompt"), {
      target: { value: "ok" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze cost/i }));

    const inputCostNode = await screen.findByText(/input cost$/);
    expect(inputCostNode.textContent).toMatch(/\$1\.70e-7\s+input cost/);
    const optimizedCostNode = screen.getByText(/optimized cost$/);
    expect(optimizedCostNode.textContent).toMatch(/^\$0\s+optimized cost/);
  });
});
