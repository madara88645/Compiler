import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import FileTree from "./FileTree";
import type { AgentPackFile } from "../types";

const files: AgentPackFile[] = [
  { path: "CLAUDE.md", content: "# Memory", kind: "claude_md" },
  { path: ".claude/agents/pr-reviewer.md", content: "agent", kind: "agents" },
];

describe("FileTree", () => {
  test("renders file rows by basename and folder rows by segment", () => {
    render(
      <FileTree files={files} selectedPath={null} onSelect={() => {}} onDownloadFile={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "CLAUDE.md" })).toBeTruthy();
    expect(screen.getByRole("button", { name: ".claude" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agents" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "pr-reviewer.md" })).toBeTruthy();
  });

  test("selecting a file calls onSelect with its full path", () => {
    const onSelect = vi.fn();
    render(
      <FileTree files={files} selectedPath={null} onSelect={onSelect} onDownloadFile={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "pr-reviewer.md" }));
    expect(onSelect).toHaveBeenCalledWith(".claude/agents/pr-reviewer.md");
  });

  test("per-file download button is named by basename and passes the file", () => {
    const onDownloadFile = vi.fn();
    render(
      <FileTree files={files} selectedPath={null} onSelect={() => {}} onDownloadFile={onDownloadFile} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Download pr-reviewer.md" }));
    expect(onDownloadFile).toHaveBeenCalledWith(files[1]);
  });
});
