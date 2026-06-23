export type Verdict = "merge" | "hold" | "split" | "rebase";
export type SignalStatus = "ok" | "gap" | "mismatch" | "stale" | "unknown" | "hit";

export type FileGroup = { name: string; files: string[] };
export type RiskyAreaHit = { category: string; file: string; reason: string };
export type TestGap = { file: string; reason: string };

export type PrSafetyReport = {
  verdict: Verdict;
  title: string;
  changed_files: { total: number; groups: FileGroup[] };
  risky_areas: { status: SignalStatus; hits: RiskyAreaHit[] };
  test_coverage: { status: SignalStatus; gaps: TestGap[]; test_files: string[] };
  branch_freshness: { status: SignalStatus; commits_behind: number | null; notes: string[] };
  scope_match: { status: SignalStatus; notes: string[] };
  recommendations: string[];
};
