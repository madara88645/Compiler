import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, test } from "vitest";

import InstallChecklist from "./InstallChecklist";
import { buildInstallChecklist } from "../installChecklist";
import type { AgentPackManifest } from "../types";

const manifest: AgentPackManifest = {
  provider: "claude",
  pack_type: "project-pack",
  download_name: "x",
  preview_order: ["claude_md", "settings", "workflow"],
  files: [
    { path: "CLAUDE.md", content: "#", kind: "claude_md" },
    { path: ".claude/settings.json", content: "{}", kind: "settings" },
    { path: ".github/workflows/claude.yml", content: "y", kind: "workflow" },
  ],
};

function Harness() {
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const sections = buildInstallChecklist(manifest);
  return (
    <InstallChecklist
      sections={sections}
      checkedIds={checkedIds}
      onToggle={(id) =>
        setCheckedIds((prev) => {
          const next = new Set(prev);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        })
      }
    />
  );
}

describe("InstallChecklist", () => {
  test("renders review/validation items as labelled checkboxes and updates progress", () => {
    render(<Harness />);
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    expect(screen.getByText(`0/${checkboxes.length} done`)).toBeTruthy();

    fireEvent.click(checkboxes[0]);
    expect(screen.getByText(`1/${checkboxes.length} done`)).toBeTruthy();
  });

  test("does not render the generatedFiles section", () => {
    render(<Harness />);
    expect(screen.queryByText(/Add CLAUDE\.md to the matching path/i)).toBeNull();
  });

  test("keeps an accessible checklist heading", () => {
    render(<Harness />);
    expect(screen.getByRole("heading", { name: "Install & review checklist" })).toBeTruthy();
  });
});
