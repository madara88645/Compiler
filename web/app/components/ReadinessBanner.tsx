"use client";

import type { ReadinessReport, ReadinessVerdict } from "../../lib/api/types";

const VERDICT_META: Record<ReadinessVerdict, { title: string; tone: string }> = {
  ready: { title: "Ready to compile", tone: "text-green-300 border-green-500/40 bg-green-500/10" },
  clarify: { title: "Clarify before compiling", tone: "text-amber-300 border-amber-500/40 bg-amber-500/10" },
  risky: { title: "Risky — review first", tone: "text-red-300 border-red-500/40 bg-red-500/10" },
  noise: { title: "Not a real task", tone: "text-zinc-300 border-zinc-500/40 bg-zinc-500/10" },
};

export default function ReadinessBanner({ report }: { report?: ReadinessReport | null }) {
  if (!report) return null;
  const meta = VERDICT_META[report.verdict];
  return (
    <div className={`rounded-xl border px-4 py-3 mb-3 ${meta.tone}`} role="status" aria-live="polite">
      <div className="text-sm font-bold">{meta.title}</div>
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
    </div>
  );
}
