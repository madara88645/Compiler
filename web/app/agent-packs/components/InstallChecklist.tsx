import { CheckCircle2 } from "lucide-react";

import type { InstallChecklistSection } from "../installChecklist";

interface InstallChecklistProps {
  sections: InstallChecklistSection[];
  downloaded?: boolean;
}

export default function InstallChecklist({ sections, downloaded = false }: InstallChecklistProps) {
  const titleId = "agent-pack-install-checklist-title";

  return (
    <section
      aria-labelledby={titleId}
      className="border-b border-white/5 px-4 py-4 sm:px-6"
    >
      <div className="rounded-2xl border border-cyan-400/20 bg-cyan-500/5 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 id={titleId} className="text-sm font-semibold text-cyan-100">
              Install &amp; review checklist
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-cyan-100/70">
              Beta output is a starting point. Use this list to install files safely in your repo.
            </p>
          </div>
          {downloaded ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
              <CheckCircle2 size={12} aria-hidden="true" />
              Downloaded
            </span>
          ) : null}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {sections.map((section) => (
            <div key={section.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
              <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400">
                {section.title}
              </h4>
              <ul className="space-y-2 text-xs leading-relaxed text-zinc-300">
                {section.items.map((item) => (
                  <li key={`${section.id}-${item}`} className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400/80" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
