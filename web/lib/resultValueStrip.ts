import type { CompileResponse, ReadinessVerdict } from "./api/types";
import { normalizeIntentPolicy } from "../app/components/intent-policy-utils";

export type ResultValuePillTone = "green" | "amber" | "red" | "blue" | "zinc";

export type ResultValuePill = {
  key: "readiness" | "clarify" | "plan" | "risk" | "critique";
  label: string;
  tone: ResultValuePillTone;
  title: string;
};

const READINESS_PILL_META: Record<ReadinessVerdict, { label: string; tone: ResultValuePillTone }> = {
  ready: { label: "Ready", tone: "green" },
  clarify: { label: "Clarify", tone: "amber" },
  risky: { label: "Risky", tone: "red" },
  noise: { label: "Not a task", tone: "zinc" },
};

const RISK_PILL_META: Record<string, { label: string; tone: ResultValuePillTone }> = {
  low: { label: "Low risk", tone: "green" },
  medium: { label: "Medium risk", tone: "amber" },
  high: { label: "High risk", tone: "red" },
};

/** Plan text uses "1. ", "2. " ... step markers (see app/emitters.py emit_plan / emit_plan_v2). */
function countPlanSteps(planText: string): number {
  const matches = planText.match(/^\d+\.\s/gm);
  return matches ? matches.length : 0;
}

/**
 * Maps a CompileResponse to a compact set of "why this output is better than
 * what you typed" pills. Every value here is derived from fields already on
 * CompileResponse — no extra API calls, no new backend fields.
 *
 * A pill is omitted entirely when its underlying signal is absent (e.g. no
 * readiness report, no policy, no critique) rather than rendered as a
 * placeholder.
 */
export function getResultValuePills(result: CompileResponse): ResultValuePill[] {
  const pills: ResultValuePill[] = [];

  if (result.readiness) {
    const meta = READINESS_PILL_META[result.readiness.verdict];
    if (meta) {
      pills.push({
        key: "readiness",
        label: meta.label,
        tone: meta.tone,
        title: "Readiness verdict from the deterministic pre-compile check.",
      });
    }

    const clarifyCount = result.readiness.questions.length;
    pills.push({
      key: "clarify",
      label: clarifyCount === 0 ? "No open questions" : `${clarifyCount} to clarify`,
      tone: clarifyCount === 0 ? "green" : "amber",
      title: "Number of clarifying questions the compiler surfaced before you spend a run.",
    });
  }

  const planText = result.plan_v2 || result.plan || "";
  const planStepCount = countPlanSteps(planText);
  if (planStepCount > 0) {
    pills.push({
      key: "plan",
      label: `${planStepCount} plan step${planStepCount === 1 ? "" : "s"}`,
      tone: "blue",
      title: "Number of steps in the generated execution plan.",
    });
  }

  const policy = result.ir_v2?.policy ?? result.ir?.policy;
  if (policy) {
    const { riskLevel } = normalizeIntentPolicy(result);
    const meta = RISK_PILL_META[riskLevel] ?? { label: `${riskLevel} risk`, tone: "zinc" as const };
    pills.push({
      key: "risk",
      label: meta.label,
      tone: meta.tone,
      title: "Detected risk level from the policy handler.",
    });
  }

  if (result.critique) {
    pills.push({
      key: "critique",
      label: `Critique ${result.critique.score}/100`,
      tone: result.critique.verdict === "REJECT" ? "red" : "green",
      title: "Self-critique score the compiler assigned to its own output.",
    });
  }

  return pills;
}
