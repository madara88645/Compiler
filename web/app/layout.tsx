import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "./components/Sidebar";
import ToastProvider from "./components/ToastProvider";

export const metadata: Metadata = {
  title: "Prompt Compiler",
  description: "Policy-aware prompt compilation and optimization",
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
