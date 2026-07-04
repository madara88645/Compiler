import { CheckCircle2 } from "lucide-react";

import type { InstallChecklistSection } from "../installChecklist";

interface InstallChecklistProps {
  sections: InstallChecklistSection[];
  checkedIds: Set<string>;
  onToggle: (id: string) => void;
  downloaded?: boolean;
}

const CHECKBOX_SECTION_IDS = new Set(["reviewFirst", "validationSteps"]);

export default function InstallChecklist({
  sections,
  checkedIds,
  onToggle,
  downloaded = false,
}: InstallChecklistProps) {
  const titleId = "agent-pack-install-checklist-title";
  const rendered = sections.filter((section) => section.id !== "generatedFiles");

  const checkboxIds = rendered
    .filter((section) => CHECKBOX_SECTION_IDS.has(section.id))
    .flatMap((section) => section.items.map((_, index) => `${section.id}-${index}`));
  const total = checkboxIds.length;
  const done = checkboxIds.filter((id) => checkedIds.has(id)).length;
  const complete = total > 0 && done === total;

  return (
    <section aria-labelledby={titleId} className="border-b border-white/5 px-4 py-4 sm:px-6">
      <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/5 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 id={titleId} className="text-sm font-semibold text-cyan-100">
              Install &amp; review checklist
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-cyan-100/70">
              Generated files are a starting point — review before committing.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {complete ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                <CheckCircle2 size={12} aria-hidden="true" />
                All steps complete
              </span>
            ) : null}
            {downloaded ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                <CheckCircle2 size={12} aria-hidden="true" />
                Downloaded
              </span>
            ) : null}
          </div>
        </div>

        {total > 0 ? (
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between text-[11px] text-cyan-100/70">
              <span>Progress</span>
              <span aria-live="polite">{`${done}/${total} done`}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-cyan-400 transition-all"
                style={{ width: `${(done / total) * 100}%` }}
              />
            </div>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          {rendered.map((section) => (
            <div key={section.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
                {section.title}
              </h4>
              {CHECKBOX_SECTION_IDS.has(section.id) ? (
                <ul className="space-y-2 text-xs leading-relaxed text-zinc-300">
                  {section.items.map((item, index) => {
                    const id = `${section.id}-${index}`;
                    return (
                      <li key={id}>
                        <label className="flex cursor-pointer gap-2">
                          <input
                            type="checkbox"
                            checked={checkedIds.has(id)}
                            onChange={() => onToggle(id)}
                            className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-cyan-400"
                          />
                          <span>{item}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <ul className="space-y-2 text-xs leading-relaxed text-zinc-300">
                  {section.items.map((item) => (
                    <li key={`${section.id}-${item}`} className="flex gap-2">
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400/80"
                        aria-hidden="true"
                      />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
