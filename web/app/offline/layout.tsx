import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Offline Compiler — Prompt Compiler",
  description:
    "A fast, local-only prompt compiler that uses deterministic heuristics instead of an LLM — secure, instant, no API keys.",
};

export default function OfflineLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
