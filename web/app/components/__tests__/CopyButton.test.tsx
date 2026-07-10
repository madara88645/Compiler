import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { copyToClipboard } from "../../lib/copyToClipboard";
import CopyButton from "../CopyButton";

// Mock the copyToClipboard utility
vi.mock("../../lib/copyToClipboard", () => ({
  copyToClipboard: vi.fn(),
}));

describe("CopyButton", () => {
  const testText = "Hello, world!";
  const testLabel = "Copy Text";

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders with default props and correct accessibility attributes", () => {
    render(<CopyButton text={testText} />);
    const button = screen.getByRole("button");

    expect(button).toBeInTheDocument();
    expect(button.getAttribute("aria-label")).toBe("Copy to Clipboard");
    expect(button.getAttribute("title")).toBe("Copy to Clipboard");
    expect(button.getAttribute("aria-live")).toBe("polite");

    // Check for the presence of the default screen reader text
    expect(screen.getByText("Copy to Clipboard")).toBeInTheDocument();

    // Verify copy icon is visible and checkmark icon is not
    expect(button.querySelector("rect")).toBeInTheDocument();
    expect(button.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("uses custom label if provided", () => {
    render(<CopyButton text={testText} label={testLabel} />);
    const button = screen.getByRole("button");

    expect(button.getAttribute("aria-label")).toBe(testLabel);
    expect(button.getAttribute("title")).toBe(testLabel);
    expect(screen.getByText(testLabel)).toBeInTheDocument();
  });

  it("calls copyToClipboard with correct text when clicked", async () => {
    vi.mocked(copyToClipboard).mockResolvedValue(true);

    render(<CopyButton text={testText} label={testLabel} />);
    const button = screen.getByRole("button");

    await act(async () => {
      fireEvent.click(button);
    });

    expect(copyToClipboard).toHaveBeenCalledWith(testText);
  });

  it("transitions to checked state upon successful copy, and reverts after 2 seconds", async () => {
    vi.mocked(copyToClipboard).mockResolvedValue(true);

    render(<CopyButton text={testText} label={testLabel} />);
    const button = screen.getByRole("button");

    // Initial state check
    expect(button.getAttribute("aria-label")).toBe(testLabel);
    expect(button.getAttribute("title")).toBe(testLabel);
    expect(button.querySelector("rect")).toBeInTheDocument();
    expect(button.querySelector("polyline")).not.toBeInTheDocument();
    expect(screen.queryByText("Copied!")).not.toBeInTheDocument();

    // Click button to initiate copy
    await act(async () => {
      fireEvent.click(button);
    });

    // Check transition state (showing checkmark icon, updated aria-label, etc.)
    expect(button.getAttribute("aria-label")).toBe("Copied");
    expect(button.getAttribute("title")).toBe("Copied!");
    expect(button.querySelector("rect")).not.toBeInTheDocument();
    expect(button.querySelector("polyline")).toBeInTheDocument();
    expect(screen.getByText("Copied!")).toBeInTheDocument();

    // Advance timer by 1999ms (should still be in copied state)
    await act(async () => {
      vi.advanceTimersByTime(1999);
    });
    expect(button.getAttribute("aria-label")).toBe("Copied");

    // Advance timer to 2000ms (should revert back to initial state)
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(button.getAttribute("aria-label")).toBe(testLabel);
    expect(button.getAttribute("title")).toBe(testLabel);
    expect(button.querySelector("rect")).toBeInTheDocument();
    expect(button.querySelector("polyline")).not.toBeInTheDocument();
    expect(screen.queryByText("Copied!")).not.toBeInTheDocument();
  });

  it("does not transition to checked state if copyToClipboard fails", async () => {
    vi.mocked(copyToClipboard).mockResolvedValue(false);

    render(<CopyButton text={testText} label={testLabel} />);
    const button = screen.getByRole("button");

    // Click button to initiate copy
    await act(async () => {
      fireEvent.click(button);
    });

    // Should remain in original state
    expect(button.getAttribute("aria-label")).toBe(testLabel);
    expect(button.getAttribute("title")).toBe(testLabel);
    expect(button.querySelector("rect")).toBeInTheDocument();
    expect(button.querySelector("polyline")).not.toBeInTheDocument();
    expect(screen.queryByText("Copied!")).not.toBeInTheDocument();
  });
});
