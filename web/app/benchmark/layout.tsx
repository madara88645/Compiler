import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Prompt Benchmark — Prompt Compiler",
  description:
    "Send a prompt to a real model twice, raw versus compiled, and compare which answer is clearer, safer, and more concise.",
};

export default function BenchmarkLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
