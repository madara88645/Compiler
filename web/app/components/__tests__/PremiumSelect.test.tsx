import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom";
import PremiumSelect from "../PremiumSelect";

describe("PremiumSelect", () => {
  it("renders with options and handles value change", () => {
    const handleChange = vi.fn();
    render(
      <PremiumSelect value="1" onChange={handleChange} focusVariant="blue">
        <option value="1">Option 1</option>
        <option value="2">Option 2</option>
      </PremiumSelect>
    );

    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("1");

    fireEvent.change(select, { target: { value: "2" } });
    expect(handleChange).toHaveBeenCalled();
  });

  it("applies correct variant classes", () => {
    const { rerender } = render(
      <PremiumSelect focusVariant="green">
        <option value="1">Option 1</option>
      </PremiumSelect>
    );
    expect(screen.getByRole("combobox").className).toContain("focus:ring-emerald-500/50");

    rerender(
      <PremiumSelect focusVariant="yellow">
        <option value="1">Option 1</option>
      </PremiumSelect>
    );
    expect(screen.getByRole("combobox").className).toContain("focus:ring-amber-500/50");
  });
});
