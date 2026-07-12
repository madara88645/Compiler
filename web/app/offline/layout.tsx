import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Offline Compiler — Prompt Compiler",
  description:
    "This route redirects to the main Compiler page. Use the Heuristics only (no LLM) engine toggle there to run the deterministic heuristic pipeline without a cloud LLM call.",
};

export default function OfflineLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
