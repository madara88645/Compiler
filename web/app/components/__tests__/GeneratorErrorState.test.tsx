import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import GeneratorErrorState from "../GeneratorErrorState";

vi.mock("@/config", () => ({
  describeRequestError: (error: unknown) =>
    error instanceof Error ? error.message : "Something went wrong",
}));

describe("GeneratorErrorState", () => {
  it("renders the error message and calls onRetry", () => {
    const onRetry = vi.fn();

    render(
      <GeneratorErrorState
        error={new Error("Cloud generator unavailable")}
        onRetry={onRetry}
        title="Agent generation failed"
        retryLabel="Retry generation"
      />,
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Agent generation failed")).toBeTruthy();
    expect(screen.getByText("Cloud generator unavailable")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Retry generation" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
