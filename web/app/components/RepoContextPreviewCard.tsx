import type { GitHubRepoContextPayload } from "@/lib/api/types";

type RepoContextPreviewCardProps = {
  repoContext: GitHubRepoContextPayload;
  accent: "green" | "yellow";
};

const accentMap = {
  green: {
    ring: "ring-green-500/20",
    badge: "bg-green-500/10 text-green-200 border-green-500/20",
    code: "text-green-300",
  },
  yellow: {
    ring: "ring-yellow-500/20",
    badge: "bg-yellow-500/10 text-yellow-200 border-yellow-500/20",
    code: "text-yellow-300",
  },
} as const;

export default function RepoContextPreviewCard({
  repoContext,
  accent,
}: RepoContextPreviewCardProps) {
  const styles = accentMap[accent];

  return (
    <div className={`rounded-2xl border border-white/10 bg-black/20 p-4 ring-1 ${styles.ring}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">
            Repo Brief
          </div>
          <div className="mt-1 text-sm font-semibold text-white">{repoContext.repo_full_name}</div>
        </div>
        {repoContext.default_branch ? (
          <span className={`rounded-full border px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${styles.badge}`}>
            {repoContext.default_branch}
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-xs leading-relaxed text-zinc-300">{repoContext.summary}</p>

      {repoContext.detected_stack.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {repoContext.detected_stack.map((item) => (
            <span
              key={item}
              className={`rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-mono uppercase tracking-wider ${styles.code}`}
            >
              {item}
            </span>
          ))}
        </div>
      ) : null}

      {repoContext.highlights.length > 0 ? (
        <div className="mt-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Highlights</div>
          <ul className="mt-2 space-y-1">
            {repoContext.highlights.map((item) => (
              <li key={item} className="text-xs leading-relaxed text-zinc-300">
                {item}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {repoContext.files_used.length > 0 ? (
        <div className="mt-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Files Used</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {repoContext.files_used.map((item) => (
              <span
                key={item}
                className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-mono text-zinc-300"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
