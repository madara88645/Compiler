import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Skill Generator — Prompt Compiler",
  description:
    "Describe a capability, and generate a structured Tool/Skill definition, with input/output schemas, ready to integrate into your AI agents.",
};

export default function SkillsGeneratorLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
