"use client";

import type { ReactNode } from "react";

import type { CompileResponse } from "../../lib/api/types";
import { humanizeIntentPolicyValue, normalizeIntentPolicy, type IntentDisplayGroup } from "./intent-policy-utils";

type IntentPolicyPanelProps = {
  result: CompileResponse;
};

function FieldLabel({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500">{children}</div>
      {hint && <div className="mt-0.5 text-[11px] leading-snug text-zinc-600">{hint}</div>}
    </div>
  );
}

function FieldList({
  title,
  items,
  emptyLabel,
  hint,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
      <div className="mb-1 text-xs font-mono uppercase tracking-[0.18em] text-zinc-500">{title}</div>
      {hint && <div className="mb-3 text-[11px] leading-snug text-zinc-600">{hint}</div>}
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-zinc-200"
            >
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-sm text-zinc-500">{emptyLabel}</div>
      )}
    </div>
  );
}

function IntentGroupBadge({ group }: { group: IntentDisplayGroup }) {
  const styles: Record<IntentDisplayGroup, string> = {
    content: "border-cyan-400/20 bg-cyan-400/10 text-cyan-100",
    workflow: "border-violet-400/20 bg-violet-400/10 text-violet-100",
    risk: "border-amber-400/20 bg-amber-400/10 text-amber-100",
  };

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.18em] ${styles[group]}`}>
      {group}
    </span>
  );
}

export default function IntentPolicyPanel({ result }: IntentPolicyPanelProps) {
  const intentPolicy = normalizeIntentPolicy(result);

  return (
    <div className="h-full overflow-y-auto p-6 text-zinc-200">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-3xl border border-cyan-500/15 bg-gradient-to-br from-cyan-500/10 to-transparent p-5">
          <div className="mb-1 text-[11px] font-mono uppercase tracking-[0.18em] text-cyan-300/80">
            Intent
          </div>
          <p className="mb-3 text-[11px] leading-snug text-cyan-200/70">
            What the compiler thinks you are trying to do.
          </p>
          <div className="space-y-3">
            <div>
              <FieldLabel hint="What kind of work this request is about (code, ops, writing, …).">Domain</FieldLabel>
              <div className="mt-1 text-lg font-semibold text-white">{intentPolicy.domain}</div>
            </div>
            <div>
              <FieldLabel hint="Who the AI should act as while answering.">Persona</FieldLabel>
              <div className="mt-1 text-sm text-zinc-200">{humanizeIntentPolicyValue(intentPolicy.persona)}</div>
            </div>
            <div>
              <FieldLabel hint="Specific intent signals the compiler picked up from your request.">Detected Intents</FieldLabel>
              <div className="mt-2">
                {intentPolicy.intentDetails.length > 0 ? (
                  <div className="grid gap-3">
                    {intentPolicy.intentDetails.map((intent) => (
                      <div
                        key={intent.key}
                        className="rounded-2xl border border-white/8 bg-black/20 p-3"
                      >
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-white">{intent.label}</div>
                          <IntentGroupBadge group={intent.group} />
                        </div>
                        <div className="text-xs leading-relaxed text-zinc-400">{intent.description}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 p-4">
                    <div className="text-sm font-medium text-white">General Request</div>
                    <div className="mt-1 text-sm text-zinc-500">
                      No special intent signals were inferred, so the compiler is treating this as a general-purpose request.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-amber-500/15 bg-gradient-to-br from-amber-500/10 to-transparent p-5">
          <div className="mb-1 text-[11px] font-mono uppercase tracking-[0.18em] text-amber-300/80">
            Policy
          </div>
          <p className="mb-3 text-[11px] leading-snug text-amber-200/70">
            Safety rules the compiler applied to this request.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <FieldLabel hint="How cautious the compiler was when shaping the output.">Risk Level</FieldLabel>
              <div className="mt-1 text-lg font-semibold text-white">{humanizeIntentPolicyValue(intentPolicy.riskLevel)}</div>
            </div>
            <div>
              <FieldLabel hint="Whether the result is meant to be run automatically or only suggested.">Execution Mode</FieldLabel>
              <div className="mt-1 text-lg font-semibold text-white">{humanizeIntentPolicyValue(intentPolicy.executionMode)}</div>
            </div>
            <div>
              <FieldLabel hint="How private the input data looked to the scanner.">Data Sensitivity</FieldLabel>
              <div className="mt-1 text-sm text-zinc-200">{humanizeIntentPolicyValue(intentPolicy.dataSensitivity)}</div>
            </div>
            <div>
              <FieldLabel hint="Categories the compiler flagged as needing extra care.">Risk Domains</FieldLabel>
              <div className="mt-1 text-sm text-zinc-200">
                {intentPolicy.riskDomains.length > 0
                  ? intentPolicy.riskDomains.map(humanizeIntentPolicyValue).join(", ")
                  : "None"}
              </div>
            </div>
          </div>
        </div>

        <FieldList
          title="Allowed Tools"
          hint="Tools the resulting agent is permitted to call."
          items={intentPolicy.allowedTools.map(humanizeIntentPolicyValue)}
          emptyLabel="No tool allowlist needed for this request."
        />
        <FieldList
          title="Forbidden Tools"
          hint="Tools the resulting agent is not permitted to call."
          items={intentPolicy.forbiddenTools.map(humanizeIntentPolicyValue)}
          emptyLabel="No explicit forbidden tools inferred."
        />
        <div className="lg:col-span-2">
          <FieldList
            title="Sanitization Rules"
            hint="Cleanups applied to the prompt before it was used."
            items={intentPolicy.sanitizationRules.map(humanizeIntentPolicyValue)}
            emptyLabel="No extra sanitization rules inferred."
          />
        </div>
      </div>
    </div>
  );
}
