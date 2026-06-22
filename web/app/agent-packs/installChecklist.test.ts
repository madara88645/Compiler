import { describe, expect, test } from "vitest";

import { buildInstallChecklist } from "./installChecklist";
import type { AgentPackManifest } from "./types";

const prReviewerManifest: AgentPackManifest = {
  provider: "claude",
  pack_type: "pr-reviewer",
  download_name: "saas-pr-reviewer-claude",
  preview_order: ["claude_md", "agents", "workflow"],
  files: [
    { path: "CLAUDE.md", content: "# Memory", kind: "claude_md" },
    { path: ".claude/agents/pr-reviewer.md", content: "agent", kind: "agents" },
    { path: ".github/workflows/claude.yml", content: "workflow", kind: "workflow" },
  ],
};

const mcpStubManifest: AgentPackManifest = {
  provider: "claude",
  pack_type: "mcp-tool-stub",
  download_name: "saas-mcp-stub-claude",
  preview_order: ["files", "readme"],
  files: [
    { path: "server.py", content: "print('hi')", kind: "files" },
    { path: "README.md", content: "setup", kind: "readme" },
  ],
};

const projectPackManifest: AgentPackManifest = {
  provider: "claude",
  pack_type: "project-pack",
  download_name: "saas-project-pack-claude",
  preview_order: ["claude_md", "settings", "agents", "workflow", "mcp"],
  files: [
    { path: "CLAUDE.md", content: "# Memory", kind: "claude_md" },
    { path: ".claude/settings.json", content: "{}", kind: "settings" },
    { path: ".claude/agents/helper.md", content: "agent", kind: "agents" },
    { path: ".github/workflows/claude.yml", content: "workflow", kind: "workflow" },
    { path: ".claude/mcp/claude-desktop.json", content: "{}", kind: "mcp" },
  ],
};

describe("buildInstallChecklist", () => {
  test("includes generated file paths from the manifest", () => {
    const sections = buildInstallChecklist(prReviewerManifest);
    const generated = sections.find((section) => section.id === "generatedFiles");

    expect(generated?.items).toEqual([
      "Add CLAUDE.md to the matching path in your repository.",
      "Add .claude/agents/pr-reviewer.md to the matching path in your repository.",
      "Add .github/workflows/claude.yml to the matching path in your repository.",
    ]);
  });

  test("flags workflow and agent files for review on pr-reviewer packs", () => {
    const sections = buildInstallChecklist(prReviewerManifest);
    const review = sections.find((section) => section.id === "reviewFirst");

    expect(review?.items.some((item) => item.includes("pr-reviewer.md"))).toBe(true);
    expect(review?.items.some((item) => item.includes("claude.yml"))).toBe(true);
  });

  test("adds executable and MCP validation guidance for mcp-tool-stub packs", () => {
    const sections = buildInstallChecklist(mcpStubManifest);
    const review = sections.find((section) => section.id === "reviewFirst");
    const validation = sections.find((section) => section.id === "validationSteps");

    expect(review?.items.some((item) => item.includes("server.py"))).toBe(true);
    expect(validation?.items.some((item) => item.includes("server code"))).toBe(true);
    expect(validation?.items.some((item) => item.includes("README"))).toBe(true);
  });

  test("includes project-pack specific validation steps", () => {
    const sections = buildInstallChecklist(projectPackManifest);
    const validation = sections.find((section) => section.id === "validationSteps");

    expect(validation?.items.some((item) => item.includes("CLAUDE.md"))).toBe(true);
    expect(validation?.items.some((item) => item.includes("settings.json"))).toBe(true);
    expect(validation?.items.some((item) => item.includes("GitHub workflow"))).toBe(true);
  });

  test("updates next-step copy after download", () => {
    const before = buildInstallChecklist(prReviewerManifest);
    const after = buildInstallChecklist(prReviewerManifest, { downloaded: true });

    expect(before.find((section) => section.id === "nextAction")?.title).toBe("Next step");
    expect(after.find((section) => section.id === "nextAction")?.title).toBe("Downloaded — next step");
    expect(after.find((section) => section.id === "nextAction")?.items[0]).toContain("Unpack the zip");
  });
});
