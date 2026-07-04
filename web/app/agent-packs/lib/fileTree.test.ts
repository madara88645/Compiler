import { describe, expect, test } from "vitest";

import { buildFileTree, type FileTreeFolderNode } from "./fileTree";
import type { AgentPackFile } from "../types";

const mk = (path: string): AgentPackFile => ({ path, content: path, kind: "files" });

describe("buildFileTree", () => {
  test("a single top-level file becomes one file node", () => {
    const tree = buildFileTree([mk("CLAUDE.md")]);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ type: "file", name: "CLAUDE.md", path: "CLAUDE.md" });
  });

  test("nested paths build folder nodes with the right segments and paths", () => {
    const tree = buildFileTree([mk(".claude/agents/pr-reviewer.md")]);
    expect(tree).toHaveLength(1);
    const claude = tree[0] as FileTreeFolderNode;
    expect(claude).toMatchObject({ type: "folder", name: ".claude", path: ".claude" });
    const agents = claude.children[0] as FileTreeFolderNode;
    expect(agents).toMatchObject({ type: "folder", name: "agents", path: ".claude/agents" });
    expect(agents.children[0]).toMatchObject({
      type: "file",
      name: "pr-reviewer.md",
      path: ".claude/agents/pr-reviewer.md",
    });
  });

  test("folders sort before files, alphabetically within a level", () => {
    const tree = buildFileTree([mk("README.md"), mk(".claude/settings.json"), mk("AGENTS.md")]);
    expect(tree.map((n) => n.name)).toEqual([".claude", "AGENTS.md", "README.md"]);
    expect(tree[0].type).toBe("folder");
  });
});
