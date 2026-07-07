import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import QualityCoach from "../QualityCoach";
import { apiJson } from "@/config";

vi.mock("@/config", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/config")>();
  return {
    ...actual,
    apiJson: vi.fn(),
  };
});

vi.mock("../../lib/showError", () => ({
  showError: vi.fn(),
}));

const apiJsonMock = vi.mocked(apiJson);

const validationResponse = {
  score: 82,
  category_scores: { clarity: 90, specificity: 70 },
  strengths: ["Clear goal"],
  weaknesses: [],
  suggestions: [],
  summary: "Looks solid.",
};

describe("QualityCoach", () => {
  beforeEach(() => {
    apiJsonMock.mockReset();
  });

  it("shows an inline error card with a retry button when analysis fails", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("Backend unreachable"));

    render(<QualityCoach prompt="Write a summary of this document" />);

    fireEvent.click(screen.getAllByRole("button", { name: "Run quality analysis" })[0]);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    expect(screen.getByText("Quality analysis failed")).toBeTruthy();
    expect(screen.getByText("Backend unreachable")).toBeTruthy();

    // The pristine empty state must not still be shown alongside the error.
    expect(
      screen.queryByText("Run analysis to detect potential improvements and safety issues."),
    ).toBeNull();

    const retryButton = screen.getByRole("button", { name: "Retry analysis" });
    expect(retryButton).toBeTruthy();

    apiJsonMock.mockResolvedValueOnce(validationResponse);
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
    expect(screen.getByText("82/100")).toBeTruthy();
  });

  it("clears a previous error once a new run starts", async () => {
    apiJsonMock.mockRejectedValueOnce(new Error("Backend unreachable"));

    render(<QualityCoach prompt="Write a summary of this document" />);

    fireEvent.click(screen.getAllByRole("button", { name: "Run quality analysis" })[0]);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });

    apiJsonMock.mockResolvedValueOnce(validationResponse);
    fireEvent.click(screen.getByRole("button", { name: "Run quality analysis" }));

    // The error card disappears immediately once a new run is kicked off.
    expect(screen.queryByRole("alert")).toBeNull();

    await waitFor(() => {
      expect(screen.getByText("82/100")).toBeTruthy();
    });
  });
});
