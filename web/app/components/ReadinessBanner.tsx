"use client";

import type { ReadinessReport, ReadinessVerdict } from "../../lib/api/types";

export const VERDICT_META: Record<
  ReadinessVerdict,
  { title: string; tone: string; dot: string; meaning: string }
> = {
  ready: {
    title: "Ready to compile",
    tone: "text-green-300 border-green-500/40 bg-green-500/10",
    dot: "bg-green-400",
    meaning: "Clear and safe — go ahead and spend the run.",
  },
  clarify: {
    title: "Clarify before compiling",
    tone: "text-amber-300 border-amber-500/40 bg-amber-500/10",
    dot: "bg-amber-400",
    meaning: "Answer a question or two first so you don't waste a run.",
  },
  risky: {
    title: "Risky — review first",
    tone: "text-red-300 border-red-500/40 bg-red-500/10",
    dot: "bg-red-400",
    meaning: "Touches something sensitive — review before running.",
  },
  noise: {
    title: "Not a real task",
    tone: "text-zinc-300 border-zinc-500/40 bg-zinc-500/10",
    dot: "bg-zinc-400",
    meaning: "Nothing concrete to compile yet.",
  },
};

export const READINESS_FOOTER =
  "Deterministic rule-based check — runs before any LLM or agent call, never guesses.";

export default function ReadinessBanner({
  report,
  variant = "full",
}: {
  report?: ReadinessReport | null;
  variant?: "full" | "compact";
}) {
  if (!report) return null;
  const meta = VERDICT_META[report.verdict];
  const compact = variant === "compact";
  return (
    <div
      className={`animate-slide-in-down rounded-xl border mb-3 ${meta.tone} ${compact ? "px-3 py-2" : "px-4 py-3"}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <span
          data-testid="readiness-dot"
          aria-hidden="true"
          className={`h-2 w-2 shrink-0 rounded-full ${meta.dot}`}
        />
        <span className="text-sm font-bold">{meta.title}</span>
      </div>
      <div className={`mt-1 text-zinc-200 opacity-90 ${compact ? "text-[11px]" : "text-xs"}`}>
        {meta.meaning}
      </div>

      {!compact && (
        <>
          {report.signals.length > 0 && (
            <ul className="mt-2 space-y-1">
              {report.signals.map((s, i) => (
                <li key={`${s.kind}-${i}`} className="text-xs text-zinc-200">{s.message}</li>
              ))}
            </ul>
          )}
          {report.questions.length > 0 && (
            <div className="mt-2">
              <div className="text-[11px] uppercase tracking-wide opacity-70">Clarify first</div>
              <ul className="mt-1 space-y-1">
                {report.questions.map((q, i) => (
                  <li key={`q-${i}`} className="text-xs text-zinc-100">· {q}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-3 border-t border-white/10 pt-2 text-[10px] text-zinc-400">
            {READINESS_FOOTER}
          </div>
        </>
      )}
    </div>
  );
}
