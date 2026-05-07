import type { AgentPackProviderConfig } from "./types";

export const agentPackProviders: AgentPackProviderConfig[] = [
  {
    id: "claude",
    name: "Claude",
    badge: "V1 Live",
    summary: "Generate repo-ready Claude assets from one short brief.",
    ctaLabel: "Generate Claude Pack",
    accentClass: "from-sky-500 via-cyan-500 to-blue-600",
    glowClass: "bg-cyan-500/20",
    buttonClass:
      "bg-gradient-to-r from-sky-500 via-cyan-500 to-blue-600 hover:from-sky-400 hover:via-cyan-400 hover:to-blue-500 focus-visible:ring-cyan-400 shadow-cyan-500/20",
  },
];
