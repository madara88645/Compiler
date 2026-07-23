import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { copyToClipboardMock } = vi.hoisted(() => ({
  copyToClipboardMock: vi.fn(),
}));

vi.mock("../../lib/copyToClipboard", () => ({
  copyToClipboard: copyToClipboardMock,
}));

import CopyButton from "../CopyButton";

const CHECKMARK_SELECTOR = "polyline[points='20 6 9 17 4 12']";
const COPY_ICON_SELECTOR = "rect[x='8'][y='8']";

async function clickAndFlush(button: HTMLElement) {
  fireEvent.click(button);
  await act(async () => {
    await Promise.resolve();
  });
}

describe("CopyButton", () => {
  beforeEach(() => {
    copyToClipboardMock.mockReset();
    copyToClipboardMock.mockResolvedValue(true);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders with default props and correct accessibility attributes", () => {
    render(<CopyButton text="hello world" />);

    const button = screen.getByRole("button", { name: "Copy to Clipboard" });
    expect(button).toHaveAttribute("aria-label", "Copy to Clipboard");
    expect(button).toHaveAttribute("title", "Copy to Clipboard");
    expect(button).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Copy to Clipboard")).toBeInTheDocument();
    expect(button.querySelector(COPY_ICON_SELECTOR)).toBeInTheDocument();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();
  });

  it("uses custom label if provided", () => {
    render(<CopyButton text="hello world" label="Copy output" />);

    const button = screen.getByRole("button", { name: "Copy output" });
    expect(button).toHaveAttribute("aria-label", "Copy output");
    expect(button).toHaveAttribute("title", "Copy output");
    expect(screen.getByText("Copy output")).toBeInTheDocument();
  });

  it("calls copyToClipboard when clicked", async () => {
    render(<CopyButton text="hello world" />);

    await clickAndFlush(screen.getByRole("button", { name: "Copy to Clipboard" }));

    expect(copyToClipboardMock).toHaveBeenCalledWith("hello world");
  });

  it("shows the checkmark icon and updated aria attributes after a successful copy, then reverts after the timeout", async () => {
    vi.useFakeTimers();

    render(<CopyButton text="payload" label="Copy output" />);

    const button = screen.getByRole("button", { name: "Copy output" });
    expect(button).toHaveAttribute("aria-label", "Copy output");
    expect(button).toHaveAttribute("aria-live", "polite");
    expect(button).toHaveAttribute("title", "Copy output");
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();

    await clickAndFlush(button);

    expect(button).toHaveAttribute("aria-label", "Copied");
    expect(button).toHaveAttribute("title", "Copied!");
    expect(screen.getByText("Copied!")).toBeInTheDocument();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(button).toHaveAttribute("aria-label", "Copy output");
    expect(button).toHaveAttribute("title", "Copy output");
    expect(screen.getByText("Copy output")).toBeInTheDocument();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();
  });

  it("does not change icon or aria attributes when copyToClipboard fails", async () => {
    copyToClipboardMock.mockResolvedValue(false);

    render(<CopyButton text="blocked" />);

    const button = screen.getByRole("button", { name: "Copy to Clipboard" });
    await clickAndFlush(button);

    expect(copyToClipboardMock).toHaveBeenCalledWith("blocked");
    expect(button).toHaveAttribute("aria-label", "Copy to Clipboard");
    expect(button).toHaveAttribute("title", "Copy to Clipboard");
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();
  });
});
