import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom";
import PremiumSelect from "../PremiumSelect";

const MOCK_OPTIONS = [
  { value: "1", label: "Option 1", description: "First option description" },
  { value: "2", label: "Option 2" },
  { value: "3", label: "Option 3", group: "Group A" },
];

describe("PremiumSelect (Custom Listbox)", () => {
  it("renders selected value", () => {
    render(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} />
    );
    expect(screen.getByRole("combobox")).toHaveTextContent("Option 1");
  });

  it("opens options list on click", () => {
    render(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} />
    );
    const trigger = screen.getByRole("combobox");

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.click(trigger);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });

  it("selects option on click and triggers onChange with selected value", () => {
    const handleChange = vi.fn();
    render(
      <PremiumSelect value="1" onChange={handleChange} options={MOCK_OPTIONS} />
    );

    fireEvent.click(screen.getByRole("combobox"));
    const listbox = screen.getByRole("listbox");
    const option2 = within(listbox).getByText("Option 2");
    fireEvent.click(option2);

    expect(handleChange).toHaveBeenCalledWith("2");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("keyboard ArrowDown + Enter selects option", () => {
    const handleChange = vi.fn();
    render(
      <PremiumSelect value="1" onChange={handleChange} options={MOCK_OPTIONS} />
    );

    const trigger = screen.getByRole("combobox");
    trigger.focus();

    // Open listbox and highlight Option 1 (first item)
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    // Move to Option 2
    fireEvent.keyDown(trigger, { key: "ArrowDown" });

    // Press Enter to select
    fireEvent.keyDown(trigger, { key: "Enter" });

    expect(handleChange).toHaveBeenCalledWith("2");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("Escape closes the options list", () => {
    render(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} />
    );
    const trigger = screen.getByRole("combobox");

    fireEvent.click(trigger);
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("disabled state does not open listbox", () => {
    render(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} disabled />
    );
    const trigger = screen.getByRole("combobox");

    fireEvent.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("applies correct focusVariant classes", () => {
    const { rerender } = render(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} focusVariant="green" />
    );
    expect(screen.getByRole("combobox").className).toContain("focus-visible:ring-emerald-500/50");

    rerender(
      <PremiumSelect value="1" onChange={() => {}} options={MOCK_OPTIONS} focusVariant="yellow" />
    );
    expect(screen.getByRole("combobox").className).toContain("focus-visible:ring-amber-500/50");
  });
});
