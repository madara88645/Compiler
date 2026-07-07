import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Token Optimizer — Prompt Compiler",
  description:
    "Shorten prompts while keeping intent, constraints, variables, and safety details visible, with OpenRouter cost estimates.",
};

export default function OptimizerLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
