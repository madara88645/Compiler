import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InstructionReviewPage from "./page";
import { apiJson } from "@/config";
import { downloadFile } from "../../lib/downloadFile";
import { unzipSync, strFromU8 } from "fflate";

vi.mock("@/config", () => ({
  apiJson: vi.fn(),
  buildGeneratorApiHeaders: (headers: HeadersInit) => headers,
  describeRequestError: (error: Error) => error.message,
}));
vi.mock("../../lib/downloadFile", () => ({ downloadFile: vi.fn() }));
vi.mock("../../lib/copyToClipboard", () => ({ copyToClipboard: vi.fn().mockResolvedValue(true) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));

const original = "# Rules\n- Keep changes small.\n- Keep changes small.\n- Never log credentials.\n";
const suggested = "# Rules\n- Keep changes small.\n- Never log credentials.\n";
const report = {
  findings: [{ kind: "duplicate_rule", severity: "info", path: "CLAUDE.md", line: 3, message: "Repeated rule.", related: [{ path: "CLAUDE.md", line: 2 }] }],
  files: [{ path: "CLAUDE.md", original, suggested, diff: "@@ -1,4 +1,3 @@\n - Keep changes small.\n-- Keep changes small.\n - Never log credentials." }],
  summary: { files_reviewed: 1 },
};

describe("Instruction review", () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(apiJson).mockResolvedValue(report); });

  it("reviews the original text and downloads it until suggestions are explicitly selected", async () => {
    render(<InstructionReviewPage />);
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: original } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    await screen.findByText("Review complete");
    expect(apiJson).toHaveBeenCalledWith("/instruction-review/analyze", expect.objectContaining({ body: JSON.stringify({ files: [{ path: "CLAUDE.md", content: original }] }) }));
    expect(screen.getByLabelText("File 1 contents")).toHaveValue(original);
    fireEvent.click(screen.getByRole("button", { name: "Download original file" }));
    expect(downloadFile).toHaveBeenLastCalledWith(original, "CLAUDE.md", "text/markdown");
    fireEvent.click(screen.getByRole("checkbox", { name: "Use the suggested version for this download" }));
    fireEvent.click(screen.getByRole("button", { name: "Download suggested file" }));
    expect(downloadFile).toHaveBeenLastCalledWith(suggested, "CLAUDE.md", "text/markdown");
    expect(screen.getByLabelText("File 1 contents")).toHaveValue(original);
  });

  it("clears old results and accepted suggestions when inputs change", async () => {
    render(<InstructionReviewPage />);
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: original } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    await screen.findByText("Review complete");
    fireEvent.click(screen.getByRole("checkbox", { name: /Use the suggested version/ }));
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: "# New rules" } });
    expect(screen.queryByText("Review complete")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
  });

  it("preserves nested file destinations inside the downloaded ZIP", async () => {
    vi.mocked(apiJson).mockResolvedValueOnce({ ...report, files: [{ ...report.files[0], path: ".claude/rules/testing.md" }] });
    render(<InstructionReviewPage />);
    fireEvent.change(screen.getByLabelText("File 1 name"), { target: { value: ".claude/rules/testing.md" } });
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: original } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    await screen.findByText("Review complete");
    fireEvent.click(screen.getByRole("button", { name: "Download original file" }));
    const [blob, filename] = vi.mocked(downloadFile).mock.calls[0];
    expect(filename).toBe("reviewed-instructions.zip");
    expect(blob).toBeInstanceOf(Blob);
    const entries = unzipSync(new Uint8Array(await (blob as Blob).arrayBuffer()));
    expect(Object.keys(entries)).toEqual([".claude/rules/testing.md"]);
    expect(strFromU8(entries[".claude/rules/testing.md"])).toBe(original);
  });

  it("keeps text intact on API failure and rejects malformed reports", async () => {
    vi.mocked(apiJson).mockRejectedValueOnce(new Error("Backend unavailable"));
    render(<InstructionReviewPage />);
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: original } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
    expect(screen.getByLabelText("File 1 contents")).toHaveValue(original);
    vi.mocked(apiJson).mockResolvedValueOnce({ files: [], findings: [] });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("unexpected response"));
    expect(screen.queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
  });

  it("validates duplicate file names before sending and supports an explicit repo file list", async () => {
    render(<InstructionReviewPage />);
    fireEvent.change(screen.getByLabelText("File 1 contents"), { target: { value: original } });
    fireEvent.click(screen.getByRole("button", { name: "Add file" }));
    fireEvent.change(screen.getByLabelText("File 2 name"), { target: { value: "CLAUDE.md" } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    expect(screen.getByRole("alert")).toHaveTextContent("unique relative name");
    expect(apiJson).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove file 2" }));
    fireEvent.change(screen.getByLabelText("Known repository files"), { target: { value: "README.md\ndocs/build.md\n" } });
    fireEvent.click(screen.getByRole("button", { name: "Review instructions", exact: true }));
    await screen.findByText("Review complete");
    const options = vi.mocked(apiJson).mock.calls[0][1];
    expect(JSON.parse(String(options?.body)).known_repo_files).toEqual(["README.md", "docs/build.md"]);
  });
});
