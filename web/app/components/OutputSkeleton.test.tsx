import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import OutputSkeleton from "./OutputSkeleton";

describe("OutputSkeleton", () => {
  it("announces compiling as an accessible busy status region", () => {
    render(<OutputSkeleton />);

    const status = screen.getByRole("status", { name: /compiling/i });
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAccessibleName("Compiling…");
    expect(screen.getByText("Compiling…")).toHaveClass("sr-only");
  });
});
