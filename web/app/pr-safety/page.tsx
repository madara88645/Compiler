"use client";

import { useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { apiJson, buildGeneratorApiHeaders } from "@/config";
import { showError } from "../lib/showError";
import { downloadFile } from "../lib/downloadFile";
import InfoButton from "../components/InfoButton";
import GeneratorErrorState from "../components/GeneratorErrorState";
import { reportToMarkdown } from "./markdown";
import type { PrSafetyReport, SignalStatus, Verdict } from "./types";

type Tone = "green" | "amber" | "blue" | "violet" | "zinc";

const TONE_CLASSES: Record<Tone, string> = {
  green: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  blue: "border-sky-400/40 bg-sky-400/10 text-sky-200",
  violet: "border-violet-400/40 bg-violet-400/10 text-violet-200",
  zinc: "border-zinc-400/30 bg-zinc-400/10 text-zinc-200",
};

const DOT_CLASSES: Record<Tone, string> = {
  green: "bg-emerald-400",
  amber: "bg-amber-400",
  blue: "bg-sky-400",
  violet: "bg-violet-400",
  zinc: "bg-zinc-400",
};

const VERDICT_VIEW: Record<Verdict, { label: string; tone: Tone; hint: string }> = {
  merge: { label: "Merge", tone: "green", hint: "No blocking safety signals detected" },
  hold: { label: "Hold", tone: "amber", hint: "Address the flagged signals before merging" },
  split: { label: "Split", tone: "blue", hint: "Break this PR into smaller, focused changes" },
  rebase: { label: "Rebase", tone: "violet", hint: "Update the branch before merging" },
};

function statusTone(status: SignalStatus): Tone {
  switch (status) {
    case "ok":
      return "green";
    case "unknown":
      return "zinc";
    default:
      return "amber";
  }
}

function StatusBadge({ status }: { status: SignalStatus }) {
  const tone = statusTone(status);
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${TONE_CLASSES[tone]}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOT_CLASSES[tone]}`} />
      {status}
    </span>
  );
}

function SectionCard({
  title,
  status,
  children,
}: {
  title: string;
  status?: SignalStatus;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
        {status ? <StatusBadge status={status} /> : null}
      </div>
      {children}
    </section>
  );
}

const EXAMPLE = {
  title: "Add password reset endpoint",
  description: "Adds POST /auth/reset to issue and consume password reset tokens.",
  changedFiles: ["app/auth/reset.py", "app/auth/tokens.py", "api/routes/auth.py"].join("\n"),
  commitsBehind: "3",
};

export default function PrSafetyPage() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [changedFilesText, setChangedFilesText] = useState("");
  const [commitsBehindText, setCommitsBehindText] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<PrSafetyReport | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);

  const isAnalyzingRef = useRef(false);

  const parsedFiles = changedFilesText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const canSubmit =
    title.trim().length > 0 &&
    description.trim().length > 0 &&
    parsedFiles.length > 0 &&
    !loading;

  const parseCommitsBehind = (): number | undefined => {
    const raw = commitsBehindText.trim();
    if (raw === "") return undefined;
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed) || parsed < 0) return undefined;
    return parsed;
  };

  const handleAnalyze = async () => {
    if (!canSubmit || isAnalyzingRef.current) return;
    isAnalyzingRef.current = true;

    setLoading(true);
    setLastError(null);
    setReport(null);

    const commitsBehind = parseCommitsBehind();
    const body = {
      title: title.trim(),
      description: description.trim(),
      changed_files: parsedFiles,
      ...(commitsBehind === undefined ? {} : { commits_behind: commitsBehind }),
    };

    try {
      const data = await apiJson<PrSafetyReport>("/pr-safety/report", {
        method: "POST",
        headers: buildGeneratorApiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(body),
      });
      setReport(data);
    } catch (e: unknown) {
      showError(e);
      setLastError(e);
    } finally {
      setLoading(false);
      isAnalyzingRef.current = false;
    }
  };

  const loadExample = () => {
    setTitle(EXAMPLE.title);
    setDescription(EXAMPLE.description);
    setChangedFilesText(EXAMPLE.changedFiles);
    setCommitsBehindText(EXAMPLE.commitsBehind);
    setReport(null);
    setLastError(null);
  };

  const copyMarkdown = () => {
    if (!report) return;
    void navigator.clipboard.writeText(reportToMarkdown(report));
    toast.success("Copied report as Markdown");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadMarkdown = () => {
    if (!report) return;
    downloadFile(reportToMarkdown(report), "pr-safety-report.md", "text/markdown");
  };

  const verdictView = report ? VERDICT_VIEW[report.verdict] : null;

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-start overflow-x-hidden bg-[#050505] p-3 py-4 sm:p-4 md:h-full md:min-h-0 md:justify-center md:overflow-hidden md:p-8">
      <div className="absolute top-[-10%] left-[-10%] h-[40vw] w-[40vw] rounded-full bg-rose-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] h-[40vw] w-[40vw] rounded-full bg-orange-600/10 blur-[120px] pointer-events-none" />

      <div className="glass flex min-h-[calc(100vh-2rem)] w-full max-w-7xl flex-col overflow-hidden rounded-2xl bg-black/40 shadow-2xl ring-1 ring-white/10 backdrop-blur-xl animate-fade-in md:h-full md:max-h-[90vh] md:rounded-3xl">
        <header className="flex flex-col gap-3 border-b border-white/5 bg-black/20 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-rose-600 to-orange-600 flex items-center justify-center text-white shadow-lg shadow-rose-500/20">
              <ShieldCheck size={18} aria-hidden="true" />
            </div>
            <div>
              <h1 className="font-semibold text-lg tracking-tight text-white">PR Safety</h1>
              <div className="text-xs text-zinc-400 font-mono tracking-wider uppercase opacity-70">
                Merge Readiness Layer
              </div>
            </div>
            <InfoButton
              title="PR Safety (offline advisory)"
              description="Paste a pull request's title, description and changed files to get an offline, deterministic merge-readiness report: verdict, risky areas, branch freshness, test coverage and scope signals. v1 is heuristic advice only — it never blocks merges and makes no GitHub or AI calls."
            />
          </div>
        </header>

        <div className="flex flex-1 flex-col overflow-visible md:min-h-0 md:flex-row md:overflow-hidden">
          {/* Input panel */}
          <div className="flex w-full flex-col gap-4 border-b border-white/5 bg-black/10 p-4 sm:p-5 md:min-h-0 md:w-[40%] md:border-b-0 md:border-r md:overflow-y-auto">
            <div className="flex flex-col gap-2">
              <label htmlFor="pr-title" className="text-sm font-medium text-zinc-300" id="pr-title-label">
                PR Title
              </label>
              <input
                id="pr-title"
                aria-labelledby="pr-title-label"
                className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-zinc-200 transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-rose-500/50"
                placeholder="e.g. Add password reset endpoint"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="pr-description" className="text-sm font-medium text-zinc-300" id="pr-description-label">
                PR Description
              </label>
              <p id="pr-description-help" className="sr-only">What does this PR do? Paste the PR body here.</p>
              <div className="relative group">
              <textarea
                id="pr-description"
                aria-labelledby="pr-description-label"
                aria-describedby="pr-description-help"
                className="min-h-20 w-full resize-none rounded-xl border border-white/10 bg-black/20 p-3 text-sm leading-relaxed text-zinc-200 transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-rose-500/50"
                placeholder="What does this PR do? Paste the PR body here."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              {description && (
                <button
                  type="button"
                  onClick={() => setDescription("")}
                  className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500/50"
                  title="Clear input"
                  aria-label="Clear input"
                >
                  Clear
                </button>
              )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="pr-changed-files" className="text-sm font-medium text-zinc-300" id="pr-changed-files-label">
                Changed Files
              </label>
              <p id="pr-changed-files-help" className="sr-only">One file path per line.</p>
              <p className="text-xs text-zinc-500">One file path per line.</p>
              <div className="relative group">
              <textarea
                id="pr-changed-files"
                aria-labelledby="pr-changed-files-label"
                aria-describedby="pr-changed-files-help"
                className="min-h-32 w-full resize-none rounded-xl border border-white/10 bg-black/20 p-3 font-mono text-xs leading-relaxed text-zinc-200 transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-rose-500/50"
                placeholder={"app/auth/login.py\napi/routes/auth.py\ntests/test_auth.py"}
                value={changedFilesText}
                onChange={(e) => setChangedFilesText(e.target.value)}
              />
              {changedFilesText && (
                <button
                  type="button"
                  onClick={() => setChangedFilesText("")}
                  className="absolute top-2 right-2 text-xs text-zinc-500 hover:text-zinc-300 bg-black/40 hover:bg-black/60 px-2 py-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500/50"
                  title="Clear input"
                  aria-label="Clear input"
                >
                  Clear
                </button>
              )}
              </div>
              <p className="text-[11px] text-zinc-600">
                {parsedFiles.length} file{parsedFiles.length === 1 ? "" : "s"} detected
              </p>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="pr-commits-behind" className="text-sm font-medium text-zinc-300" id="pr-commits-behind-label">
                Commits Behind
              </label>
              <p id="pr-commits-behind-help" className="sr-only">Optional. How many commits the branch is behind its base.</p>
              <p className="text-xs text-zinc-500">
                Optional. How many commits the branch is behind its base.
              </p>
              <input
                id="pr-commits-behind"
                aria-label="Commits Behind"
                type="number"
                min={0}
                inputMode="numeric"
                className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-zinc-200 transition-all placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-rose-500/50"
                placeholder="e.g. 12"
                value={commitsBehindText}
                onChange={(e) => setCommitsBehindText(e.target.value)}
              />
            </div>

            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!canSubmit}
              aria-busy={loading}
              className="w-full rounded-xl bg-gradient-to-r from-rose-600 to-orange-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-rose-500/20 transition-all hover:from-rose-500 hover:to-orange-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
            >
              {loading ? <span className="animate-pulse">Analyzing PR...</span> : "Analyze PR"}
            </button>

            <button
              type="button"
              onClick={loadExample}
              className="text-xs text-rose-300/80 transition-colors hover:text-rose-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500 rounded px-2 py-1"
            >
              or load an example
            </button>
          </div>

          {/* Output panel */}
          <div className="relative flex min-h-[360px] w-full flex-col bg-black/20 md:min-h-0 md:w-[60%] md:overflow-y-auto">
            {loading ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
                <span className="animate-pulse text-sm font-medium text-rose-300/90">
                  Analyzing merge readiness...
                </span>
              </div>
            ) : lastError ? (
              <GeneratorErrorState
                error={lastError}
                onRetry={() => void handleAnalyze()}
                title="PR Safety analysis failed"
                retryLabel="Retry analysis"
              />
            ) : report && verdictView ? (
              <div className="flex flex-col gap-4 p-4 sm:p-5">
                {/* Verdict */}
                <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                      Verdict
                    </div>
                    <div
                      data-testid="pr-verdict"
                      className={`mt-1 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold uppercase tracking-wide ${TONE_CLASSES[verdictView.tone]}`}
                    >
                      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${DOT_CLASSES[verdictView.tone]}`} />
                      {verdictView.label}
                    </div>
                    <p className="mt-2 text-xs text-zinc-400">{verdictView.hint}</p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <div className="text-xs text-zinc-500">
                      {report.changed_files.total} file
                      {report.changed_files.total === 1 ? "" : "s"} changed
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={copyMarkdown}
                        className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-200 transition-colors hover:bg-rose-500/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500"
                      >
                        <span className="sr-only" aria-live="polite">{copied ? "Copied to clipboard" : ""}</span>
                        {copied ? "Copied!" : "Copy as Markdown"}
                      </button>
                      <button
                        type="button"
                        onClick={downloadMarkdown}
                        className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500"
                      >
                        Download .md
                      </button>
                    </div>
                  </div>
                </div>

                {/* Changed files */}
                <SectionCard title="Changed files">
                  {report.changed_files.groups.length === 0 ? (
                    <p className="text-xs text-zinc-500">No files provided.</p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {report.changed_files.groups.map((group) => (
                        <div key={group.name}>
                          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                            {group.name}
                          </div>
                          <ul className="flex flex-col gap-0.5">
                            {group.files.map((file) => (
                              <li key={file} className="font-mono text-[11px] text-zinc-300">
                                {file}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </SectionCard>

                {/* Risky areas */}
                <SectionCard title="Risky areas" status={report.risky_areas.status}>
                  {report.risky_areas.hits.length === 0 ? (
                    <p className="text-xs text-zinc-500">No risky areas detected.</p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {report.risky_areas.hits.map((hit) => (
                        <li
                          key={`${hit.category}-${hit.file}`}
                          className="rounded-lg border border-amber-400/20 bg-amber-400/5 px-3 py-2"
                        >
                          <div className="flex items-center gap-2">
                            <span className="rounded bg-amber-400/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
                              {hit.category}
                            </span>
                            <span className="font-mono text-[11px] text-zinc-300">{hit.file}</span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-400">{hit.reason}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>

                {/* Test coverage */}
                <SectionCard title="Test coverage" status={report.test_coverage.status}>
                  {report.test_coverage.gaps.length === 0 ? (
                    <p className="text-xs text-zinc-500">
                      No missing test coverage detected for changed source files.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {report.test_coverage.gaps.map((gap) => (
                        <li key={gap.file} className="text-xs text-zinc-300">
                          <span className="font-mono text-[11px] text-zinc-200">{gap.file}</span>
                          <span className="block text-zinc-500">{gap.reason}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>

                {/* Branch freshness */}
                <SectionCard title="Branch freshness" status={report.branch_freshness.status}>
                  <div className="flex flex-col gap-1">
                    {report.branch_freshness.commits_behind !== null ? (
                      <p className="text-xs text-zinc-300">
                        {report.branch_freshness.commits_behind} commit
                        {report.branch_freshness.commits_behind === 1 ? "" : "s"} behind base
                      </p>
                    ) : null}
                    {report.branch_freshness.notes.map((note) => (
                      <p key={note} className="text-xs text-zinc-500">
                        {note}
                      </p>
                    ))}
                  </div>
                </SectionCard>

                {/* Scope match */}
                <SectionCard title="Scope match" status={report.scope_match.status}>
                  {report.scope_match.notes.length === 0 ? (
                    <p className="text-xs text-zinc-500">
                      Changed files line up with the PR title and description.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-1">
                      {report.scope_match.notes.map((note) => (
                        <li key={note} className="text-xs text-zinc-400">
                          {note}
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>

                {/* Recommendations */}
                <SectionCard title="Recommendations">
                  {report.recommendations.length === 0 ? (
                    <p className="text-xs text-zinc-500">No recommendations.</p>
                  ) : (
                    <ul className="flex list-disc flex-col gap-1 pl-5">
                      {report.recommendations.map((rec) => (
                        <li key={rec} className="text-xs text-zinc-300">
                          {rec}
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6 text-center text-zinc-600 sm:p-10">
                <div className="relative">
                  <div className="absolute inset-0 rounded-full bg-rose-500/20 blur-[40px]" />
                  <div className="relative flex h-24 w-24 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-zinc-800 to-black shadow-2xl">
                    <ShieldCheck size={40} strokeWidth={1.5} aria-hidden="true" className="text-rose-400/60" />
                  </div>
                </div>
                <div className="max-w-xs space-y-2">
                  <h3 className="font-medium tracking-wide text-zinc-200">Merge Readiness Check</h3>
                  <p className="text-sm text-zinc-500">
                    Paste a PR&apos;s title, description and changed files on the left, then analyze
                    it for an offline merge-readiness report.
                  </p>
                  <button
                    type="button"
                    onClick={loadExample}
                    className="mt-2 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-200 transition-colors hover:bg-rose-500/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-rose-500"
                  >
                    Load an example
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
