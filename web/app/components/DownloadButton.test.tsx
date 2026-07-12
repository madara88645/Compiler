import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { downloadFileMock } = vi.hoisted(() => ({
  downloadFileMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../lib/downloadFile", () => ({
  downloadFile: downloadFileMock,
}));

import { toast } from "sonner";
import DownloadButton from "./DownloadButton";

const CHECKMARK_SELECTOR = "polyline[points='20 6 9 17 4 12']";

describe("DownloadButton", () => {
  beforeEach(() => {
    downloadFileMock.mockClear();
    vi.mocked(toast.success).mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls downloadFile and shows a success toast when clicked", () => {
    render(
      <DownloadButton
        content="file content"
        filename="report.txt"
        mimeType="text/plain"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Download report.txt" }));

    expect(downloadFileMock).toHaveBeenCalledWith("file content", "report.txt", "text/plain");
    expect(toast.success).toHaveBeenCalledWith("Downloaded report.txt");
  });

  it("shows the checkmark icon and updated aria attributes after click, then reverts after the timeout", async () => {
    render(
      <DownloadButton content="data" filename="output.md" mimeType="text/markdown" />,
    );

    const button = screen.getByRole("button", { name: "Download output.md" });
    expect(button).toHaveAttribute("aria-label", "Download output.md");
    expect(button).toHaveAttribute("aria-live", "polite");
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-label", "Downloaded");
    expect(button).toHaveAttribute("title", "Downloaded!");
    expect(screen.getByText("Downloaded!")).toBeInTheDocument();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(button).toHaveAttribute("aria-label", "Download output.md");
    expect(button).toHaveAttribute("title", "Download (output.md)");
    expect(screen.getByText("Download")).toBeInTheDocument();
    expect(button.querySelector(CHECKMARK_SELECTOR)).toBeNull();
  });
});
