"use client";

import type { CompileResponse } from "../../lib/api/types";
import { humanizeIntentPolicyValue, normalizeIntentPolicy } from "./intent-policy-utils";

type PolicyBadgeProps = {
  result: CompileResponse;
};

type Tone = "green" | "amber" | "blue" | "zinc";

const TONE_CLASSES: Record<Tone, string> = {
  green: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  amber: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  blue: "border-sky-400/40 bg-sky-400/10 text-sky-200",
  zinc: "border-zinc-400/30 bg-zinc-400/10 text-zinc-200",
};

const DOT_CLASSES: Record<Tone, string> = {
  green: "bg-emerald-400",
  amber: "bg-amber-400",
  blue: "bg-sky-400",
  zinc: "bg-zinc-400",
};

type ModeView = { label: string; tone: Tone };

function viewForMode(mode: string): ModeView {
  switch (mode) {
    case "auto_ok":
      return { label: "Auto OK", tone: "green" };
    case "human_approval_required":
      return { label: "Approval Required", tone: "amber" };
    case "advice_only":
      return { label: "Advice Only", tone: "blue" };
    default:
      return { label: humanizeIntentPolicyValue(mode), tone: "zinc" };
  }
}

export default function PolicyBadge({ result }: PolicyBadgeProps) {
  const policy = result?.ir_v2?.policy ?? result?.ir?.policy;
  if (!policy) {
    return null;
  }

  const { executionMode, riskLevel, riskDomains } = normalizeIntentPolicy(result);
  const { label, tone } = viewForMode(executionMode);
  const domainText = riskDomains.length > 0 ? riskDomains.slice(0, 2).join(", ") : "none";
  const tooltip = `Risk: ${riskLevel} · Domains: ${domainText}`;

  return (
    <div
      aria-label={`Policy verdict: ${label}`}
      title={tooltip}
      data-testid="policy-badge"
      data-tone={tone}
      className={`animate-fade-in inline-flex shrink-0 items-center gap-1.5 self-center rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${TONE_CLASSES[tone]}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${DOT_CLASSES[tone]}`} />
      <span>{label}</span>
    </div>
  );
}
