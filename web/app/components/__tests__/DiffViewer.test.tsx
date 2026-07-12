import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockSanitize = vi.hoisted(() => vi.fn((html: string) => html));

vi.mock("dompurify", () => ({
  default: {
    sanitize: (html: string) => mockSanitize(html),
  },
}));

import DiffViewer from "../DiffViewer";

describe("DiffViewer", () => {
  beforeEach(() => {
    mockSanitize.mockReset();
    mockSanitize.mockImplementation((html: string) => html);
  });

  it("shows a loading state before sanitized diff HTML is ready", () => {
    render(<DiffViewer oldText="hello" newText="hello world" />);

    expect(screen.getByText("Semantic Diff")).toBeTruthy();
    expect(screen.getByText("Loading diff...")).toBeTruthy();
  });

  it("renders sanitized diff HTML after DOMPurify loads", async () => {
    mockSanitize.mockImplementation((html: string) =>
      html.replace(/<script[\s\S]*?<\/script>/gi, ""),
    );

    render(<DiffViewer oldText="hello" newText="hello world" />);

    await waitFor(() => {
      expect(mockSanitize).toHaveBeenCalledTimes(1);
    });

    const sanitizeInput = mockSanitize.mock.calls[0]?.[0] as string;
    expect(sanitizeInput).toContain('class="diff-equal"');
    expect(sanitizeInput).toContain('class="diff-added"');
    expect(sanitizeInput).toContain("hello");
    expect(sanitizeInput).toContain(" world");

    await waitFor(() => {
      expect(screen.queryByText("Loading diff...")).toBeNull();
    });

    const diffContent = document.querySelector(".diff-content");
    expect(diffContent).toBeTruthy();
    expect(diffContent?.innerHTML).toContain("diff-added");
    expect(diffContent?.innerHTML).toContain(" world");
    expect(diffContent?.innerHTML).not.toContain("<script");
  });

  it("shows a secure fallback when DOMPurify fails to load", async () => {
    vi.resetModules();

    vi.doMock("dompurify", () => {
      throw new Error("Network error loading DOMPurify");
    });

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const { default: DiffViewerFresh } = await import("../DiffViewer");

    render(<DiffViewerFresh oldText="alpha" newText="beta" />);

    await waitFor(() => {
      expect(
        screen.getByText("Error: Diff viewer failed to initialize securely."),
      ).toBeTruthy();
    });

    expect(consoleError).toHaveBeenCalledWith(
      "Failed to load DOMPurify:",
      expect.any(Error),
    );

    consoleError.mockRestore();
    vi.doUnmock("dompurify");
    vi.resetModules();
  });

  it("shows a secure fallback when sanitization throws", async () => {
    mockSanitize.mockImplementation(() => {
      throw new Error("sanitize failed");
    });

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(<DiffViewer oldText="alpha" newText="beta" />);

    await waitFor(() => {
      expect(
        screen.getByText("Error: Diff viewer failed to initialize securely."),
      ).toBeTruthy();
    });

    expect(consoleError).toHaveBeenCalledWith(
      "Failed to load DOMPurify:",
      expect.any(Error),
    );

    consoleError.mockRestore();
  });
});
