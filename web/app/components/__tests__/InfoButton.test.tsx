import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import InfoButton from "../InfoButton";

describe("InfoButton", () => {
  it("initially does not show the tooltip and does not have aria-describedby", () => {
    render(<InfoButton title="Test Title" description="Test Description" />);

    const button = screen.getByRole("button", { name: "More information" });
    expect(button).toBeInTheDocument();
    expect(button).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows the tooltip on mouseEnter and hides it on mouseLeave", () => {
    render(<InfoButton title="Test Title" description="Test Description" />);

    const button = screen.getByRole("button", { name: "More information" });

    fireEvent.mouseEnter(button);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveTextContent("Test Title");
    expect(tooltip).toHaveTextContent("Test Description");

    fireEvent.mouseLeave(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows the tooltip on focus and hides it on blur", () => {
    render(<InfoButton title="Test Title" description="Test Description" />);

    const button = screen.getByRole("button", { name: "More information" });

    fireEvent.focus(button);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveTextContent("Test Title");
    expect(tooltip).toHaveTextContent("Test Description");

    fireEvent.blur(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("toggles the tooltip state on click", () => {
    render(<InfoButton title="Test Title" description="Test Description" />);

    const button = screen.getByRole("button", { name: "More information" });

    fireEvent.click(button);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("associates the button with the tooltip using aria-describedby matching the tooltip ID", () => {
    render(<InfoButton title="Test Title" description="Test Description" />);

    const button = screen.getByRole("button", { name: "More information" });

    fireEvent.focus(button);

    const tooltip = screen.getByRole("tooltip");
    const tooltipId = tooltip.getAttribute("id");

    expect(tooltipId).toBeTruthy();
    expect(button).toHaveAttribute("aria-describedby", tooltipId);
  });

  it("renders correctly without a title", () => {
    render(<InfoButton description="Only Description" />);

    const button = screen.getByRole("button", { name: "More information" });
    fireEvent.focus(button);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveTextContent("Only Description");

    const strongElement = tooltip.querySelector("strong");
    expect(strongElement).toBeNull();
  });
});
