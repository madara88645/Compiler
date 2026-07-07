"use client";

import type { CompileResponse } from "../../lib/api/types";
import { getResultValuePills, type ResultValuePillTone } from "../../lib/resultValueStrip";

type ResultValueStripProps = {
  result: CompileResponse;
};

const TONE_CLASSES: Record<ResultValuePillTone, string> = {
  green: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  red: "border-red-400/40 bg-red-400/10 text-red-200",
  blue: "border-sky-400/40 bg-sky-400/10 text-sky-200",
  zinc: "border-zinc-400/30 bg-zinc-400/10 text-zinc-200",
};

const DOT_CLASSES: Record<ResultValuePillTone, string> = {
  green: "bg-emerald-400",
  amber: "bg-amber-400",
  red: "bg-red-400",
  blue: "bg-sky-400",
  zinc: "bg-zinc-400",
};

/**
 * Compact "why this beats what you typed" stat strip: readiness verdict,
 * clarify-question count, plan step count, detected risk level, and
 * critique score — all derived from the existing CompileResponse, nothing
 * fetched or computed server-side just for this UI.
 */
export default function ResultValueStrip({ result }: ResultValueStripProps) {
  const pills = getResultValuePills(result);
  if (pills.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="result-value-strip"
      role="list"
      aria-label="Compile result summary"
      className="animate-fade-in flex flex-wrap items-center gap-1.5 px-4 pt-3"
    >
      {pills.map((pill) => (
        <span
          key={pill.key}
          role="listitem"
          title={pill.title}
          data-testid={`result-value-pill-${pill.key}`}
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${TONE_CLASSES[pill.tone]}`}
        >
          <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOT_CLASSES[pill.tone]}`} />
          <span>{pill.label}</span>
        </span>
      ))}
    </div>
  );
}
