import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadFile } from "./downloadFile";

describe("downloadFile", () => {
  const createObjectURL = vi.fn(() => "blob:mock-url");
  const revokeObjectURL = vi.fn();
  const originalCreateElement = document.createElement.bind(document);
  let clickSpy: ReturnType<typeof vi.fn>;
  let lastAnchor: HTMLAnchorElement | null;

  beforeEach(() => {
    vi.useFakeTimers();
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
    URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as unknown as typeof URL.revokeObjectURL;

    clickSpy = vi.fn();
    lastAnchor = null;
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName === "a") {
        element.click = clickSpy;
        lastAnchor = element as HTMLAnchorElement;
      }
      return element;
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("creates a Blob with the given content and mime type, and clicks a download anchor", () => {
    downloadFile("hello world", "greeting.txt", "text/plain");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/plain");

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.runOnlyPendingTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("defaults to text/plain when no mime type is provided", () => {
    downloadFile("content", "file.txt");

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe("text/plain");
  });

  it("sets the anchor's download attribute to the given filename", () => {
    downloadFile("data", "compile-result.json", "application/json");

    expect(lastAnchor?.download).toBe("compile-result.json");
  });

  it("preserves an existing binary Blob and its content type", () => {
    const archive = new Blob([new Uint8Array([80, 75, 3, 4])], { type: "application/zip" });
    downloadFile(archive, "instructions.zip");
    expect(createObjectURL).toHaveBeenCalledWith(archive);
    expect(lastAnchor?.download).toBe("instructions.zip");
  });
});
