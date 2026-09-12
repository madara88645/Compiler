export type InstructionFile = { path: string; content: string };
export type InstructionFinding = {
  kind: string;
  severity: "info" | "warning" | "error";
  message: string;
  path: string;
  line: number;
  related?: { path: string; line: number }[];
};
export type ReviewedInstructionFile = { path: string; original: string; suggested: string; diff: string };
export type InstructionReview = {
  findings: InstructionFinding[];
  files: ReviewedInstructionFile[];
  summary: Record<string, number>;
};

function isRelativeFileName(path: string): boolean {
  return path.length > 0 && path.length <= 240 && !/[\\\u0000-\u001f:]/.test(path) &&
    path.split("/").every((part) => part !== "" && part !== "." && part !== "..");
}

export function isInstructionReview(value: unknown): value is InstructionReview {
  if (!value || typeof value !== "object") return false;
  const result = value as InstructionReview;
  return Array.isArray(result.files) && result.files.length > 0 && result.files.every((file) =>
    file && [file.path, file.original, file.suggested, file.diff].every((entry) => typeof entry === "string") &&
    isRelativeFileName(file.path)) && new Set(result.files.map((file) => file.path)).size === result.files.length &&
    Array.isArray(result.findings) && result.findings.every((finding) => finding &&
      typeof finding.message === "string" && typeof finding.path === "string" && typeof finding.kind === "string" &&
      ["info", "warning", "error"].includes(finding.severity) && Number.isInteger(finding.line) && finding.line > 0 &&
      (finding.related === undefined || (Array.isArray(finding.related) && finding.related.every((item) =>
        item && typeof item.path === "string" && Number.isInteger(item.line) && item.line > 0))));
}
