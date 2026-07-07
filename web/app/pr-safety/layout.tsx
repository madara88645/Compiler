import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PR Safety — Prompt Compiler",
  description:
    "Paste a pull request's title, description, and changed files for an offline, deterministic merge-readiness report — advisory only.",
};

export default function PrSafetyLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
