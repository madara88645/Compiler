import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DownloadButton from "./DownloadButton";

vi.mock("../lib/downloadFile", () => ({
  downloadFile: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn() },
}));

import { downloadFile } from "../lib/downloadFile";
import { toast } from "sonner";

describe("DownloadButton", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("renders with default label and aria-label", () => {
    render(<DownloadButton content="hello" filename="test.txt" />);
    const btn = screen.getByRole("button", { name: "Download test.txt" });
    expect(btn).toBeInTheDocument();
  });

  it("calls downloadFile and shows toast on click", () => {
    render(
      <DownloadButton
        content="file content"
        filename="output.md"
        mimeType="text/markdown"
      />,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(downloadFile).toHaveBeenCalledWith(
      "file content",
      "output.md",
      "text/markdown",
    );
    expect(toast.success).toHaveBeenCalledWith("Downloaded output.md");
  });

  it("switches to checkmark icon after click and reverts after 2000ms", () => {
    render(<DownloadButton content="x" filename="f.txt" />);
    const btn = screen.getByRole("button");

    // Before click: download icon with sr-only "Download" text
    expect(screen.getByText("Download")).toBeInTheDocument();

    fireEvent.click(btn);

    // After click: checkmark icon with sr-only "Downloaded!" text
    expect(screen.getByText("Downloaded!")).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Downloaded");

    // After timeout: reverts back
    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText("Download")).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Download f.txt");
  });

  it("applies gray variant classes by default", () => {
    render(<DownloadButton content="x" filename="f.txt" />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-zinc-700");
  });

  it("applies default (blue) variant classes when specified", () => {
    render(<DownloadButton content="x" filename="f.txt" variant="default" />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-blue-600");
  });

  it("accepts a custom label", () => {
    render(<DownloadButton content="x" filename="f.txt" label="Export" />);
    expect(screen.getByRole("button", { name: "Export f.txt" })).toBeInTheDocument();
  });
});
