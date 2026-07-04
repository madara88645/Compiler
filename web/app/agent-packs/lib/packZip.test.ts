import { describe, expect, test } from "vitest";
import { unzipSync, strFromU8 } from "fflate";

import { zipPackBytes, buildPackZip } from "./packZip";
import type { AgentPackFile } from "../types";

const files: AgentPackFile[] = [
  { path: "CLAUDE.md", content: "# Memory\n", kind: "claude_md" },
  { path: ".claude/agents/pr-reviewer.md", content: "review agent", kind: "agents" },
];

describe("packZip", () => {
  test("round-trips every file path and content", () => {
    const unzipped = unzipSync(zipPackBytes(files));
    expect(Object.keys(unzipped).sort()).toEqual(
      [".claude/agents/pr-reviewer.md", "CLAUDE.md"].sort(),
    );
    expect(strFromU8(unzipped["CLAUDE.md"])).toBe("# Memory\n");
    expect(strFromU8(unzipped[".claude/agents/pr-reviewer.md"])).toBe("review agent");
  });

  test("buildPackZip returns an application/zip Blob", () => {
    expect(buildPackZip(files).type).toBe("application/zip");
  });

  test("empty file list produces a valid empty zip", () => {
    expect(Object.keys(unzipSync(zipPackBytes([])))).toEqual([]);
  });
});
