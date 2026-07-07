import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Packs — Prompt Compiler",
  description:
    "Turn one short brief into runnable, repo-ready assets, Claude-first, review every generated file before production use.",
};

export default function AgentPacksLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
