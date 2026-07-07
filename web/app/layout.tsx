import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "./components/Sidebar";
import ToastProvider from "./components/ToastProvider";

const TAGLINE = "Catch weak prompts before you spend an agent run";

export const metadata: Metadata = {
  title: "Prompt Compiler",
  description: TAGLINE,
  openGraph: {
    title: "Prompt Compiler",
    description: TAGLINE,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Prompt Compiler",
    description: TAGLINE,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        <ToastProvider />
        <div className="flex h-screen bg-[#050505] text-zinc-300 overflow-hidden">
          {/* Sidebar Navigation */}
          <Sidebar />

          {/* Main Content Area */}
          <div className="flex-1 overflow-auto relative">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
