import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Generator — Prompt Compiler",
  description:
    "Define a role or task, and architect a comprehensive, constraint-driven system prompt for an autonomous AI agent or multi-agent swarm.",
};

export default function AgentGeneratorLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
