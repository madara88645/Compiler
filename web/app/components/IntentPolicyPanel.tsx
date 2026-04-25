"use client";

import type { CompileResponse } from "../../lib/api/types";
import { humanizeIntentPolicyValue, normalizeIntentPolicy, type IntentDisplayGroup } from "./intent-policy-utils";

type IntentPolicyPanelProps = {
  result: CompileResponse;
};

function FieldList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
}) {
  return (
    <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
      <div className="mb-3 text-xs font-mono uppercase tracking-[0.18em] text-zinc-500">{title}</div>
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
          <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.18em] text-cyan-300/80">
            Intent
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-xs text-zinc-500">Domain</div>
              <div className="text-lg font-semibold text-white">{intentPolicy.domain}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Persona</div>
              <div className="text-sm text-zinc-200">{humanizeIntentPolicyValue(intentPolicy.persona)}</div>
            </div>
            <div>
              <div className="mb-2 text-xs text-zinc-500">Detected Intents</div>
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

        <div className="rounded-3xl border border-amber-500/15 bg-gradient-to-br from-amber-500/10 to-transparent p-5">
          <div className="mb-2 text-[11px] font-mono uppercase tracking-[0.18em] text-amber-300/80">
            Policy
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="text-xs text-zinc-500">Risk Level</div>
              <div className="mt-1 text-lg font-semibold text-white">{humanizeIntentPolicyValue(intentPolicy.riskLevel)}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Execution Mode</div>
              <div className="mt-1 text-lg font-semibold text-white">{humanizeIntentPolicyValue(intentPolicy.executionMode)}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Data Sensitivity</div>
              <div className="mt-1 text-sm text-zinc-200">{humanizeIntentPolicyValue(intentPolicy.dataSensitivity)}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Risk Domains</div>
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
          items={intentPolicy.allowedTools.map(humanizeIntentPolicyValue)}
          emptyLabel="No tool allowlist needed for this request."
        />
        <FieldList
          title="Forbidden Tools"
          items={intentPolicy.forbiddenTools.map(humanizeIntentPolicyValue)}
          emptyLabel="No explicit forbidden tools inferred."
        />
        <div className="lg:col-span-2">
          <FieldList
            title="Sanitization Rules"
            items={intentPolicy.sanitizationRules.map(humanizeIntentPolicyValue)}
            emptyLabel="No extra sanitization rules inferred."
          />
        </div>
      </div>
    </div>
  );
}
