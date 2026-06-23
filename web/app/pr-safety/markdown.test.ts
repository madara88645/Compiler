import { describe, expect, test } from "vitest";

import { reportToMarkdown } from "./markdown";
import type { PrSafetyReport } from "./types";

const HOLD_REPORT: PrSafetyReport = {
  verdict: "hold",
  title: "Add login endpoint",
  changed_files: {
    total: 2,
    groups: [{ name: "auth", files: ["app/auth/login.py", "app/auth/session.py"] }],
  },
  risky_areas: {
    status: "hit",
    hits: [
      { category: "auth", file: "app/auth/login.py", reason: "Touches authentication code" },
    ],
  },
  test_coverage: {
    status: "gap",
    gaps: [{ file: "app/auth/login.py", reason: "Source file changed without a matching test file" }],
    test_files: [],
  },
  branch_freshness: {
    status: "unknown",
    commits_behind: null,
    notes: ["Branch freshness was not provided"],
  },
  scope_match: { status: "ok", notes: [] },
  recommendations: ["Hold merge until the flagged safety signals are addressed"],
};

const MERGE_REPORT: PrSafetyReport = {
  verdict: "merge",
  title: "Update docs",
  changed_files: { total: 1, groups: [{ name: "docs", files: ["README.md"] }] },
  risky_areas: { status: "ok", hits: [] },
  test_coverage: { status: "ok", gaps: [], test_files: [] },
  branch_freshness: { status: "ok", commits_behind: 1, notes: ["Branch is 1 commits behind the base branch"] },
  scope_match: { status: "ok", notes: [] },
  recommendations: ["No blocking safety signals detected; proceed with normal review"],
};

describe("reportToMarkdown", () => {
  test("renders verdict, all sections and a footer for a hold report", () => {
    const md = reportToMarkdown(HOLD_REPORT);

    expect(md).toContain("# PR Safety Report");
    expect(md).toMatch(/\*\*Verdict:\*\*\s*HOLD/);
    expect(md).toContain("Add login endpoint");

    // section headings (acceptance criteria)
    expect(md).toContain("## Changed files (2)");
    expect(md).toContain("### auth");
    expect(md).toContain("`app/auth/login.py`");
    expect(md).toContain("## Risky areas");
    expect(md).toContain("**auth**");
    expect(md).toContain("Touches authentication code");
    expect(md).toContain("## Test coverage");
    expect(md).toContain("Source file changed without a matching test file");
    expect(md).toContain("## Branch freshness");
    expect(md).toContain("Branch freshness was not provided");
    expect(md).toContain("## Scope match");
    expect(md).toContain("## Recommendations");
    expect(md).toContain("Hold merge until the flagged safety signals are addressed");

    // status signals are surfaced
    expect(md).toContain("(status: hit)");
    expect(md).toContain("(status: gap)");

    // advisory footer
    expect(md).toContain("offline heuristic advisory");
  });

  test("renders safe placeholders for a clean merge report", () => {
    const md = reportToMarkdown(MERGE_REPORT);

    expect(md).toMatch(/\*\*Verdict:\*\*\s*MERGE/);
    expect(md).toContain("1 commit");
    expect(md).toContain("No risky areas detected");
    expect(md).toContain("No missing test coverage detected");
  });
});
