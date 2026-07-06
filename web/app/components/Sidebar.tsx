"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Code2,
    Sparkles,
    WifiOff,
    Swords,
    Bot,
    Zap,
    FolderArchive,
    ShieldCheck,
    Github,
    Terminal,
    Blocks,
    Plug,
    type LucideIcon,
} from "lucide-react";

const navItems: { name: string; path: string; Icon: LucideIcon }[] = [
    { name: "Compiler",          path: "/",                 Icon: Code2    },
    { name: "Optimizer",         path: "/optimizer",        Icon: Sparkles },
    { name: "Offline",           path: "/offline",          Icon: WifiOff  },
    { name: "Benchmark",         path: "/benchmark",        Icon: Swords   },
    { name: "PR Safety",         path: "/pr-safety",        Icon: ShieldCheck },
    { name: "Agent Packs",       path: "/agent-packs",      Icon: FolderArchive },
    { name: "Agent Generator",   path: "/agent-generator",  Icon: Bot      },
    { name: "Skills Generator",  path: "/skills-generator", Icon: Zap      },
];

const outboundLinks: { name: string; href: string; Icon: LucideIcon }[] = [
    {
        name: "GitHub repo",
        href: "https://github.com/madara88645/Compiler",
        Icon: Github,
    },
    {
        name: "CLI install",
        href: "https://github.com/madara88645/Compiler/blob/main/docs/cli.md",
        Icon: Terminal,
    },
    {
        name: "VS Code extension",
        href: "https://marketplace.visualstudio.com/items?itemName=madara88645.promptc-vscode",
        Icon: Blocks,
    },
    {
        name: "MCP setup",
        href: "https://github.com/madara88645/Compiler/blob/main/integrations/mcp-server/README.md",
        Icon: Plug,
    },
];

const accentBarMap: Record<string, string> = {
    "/":                  "bg-blue-500",
    "/optimizer":         "bg-emerald-500",
    "/offline":           "bg-zinc-500",
    "/benchmark":         "bg-amber-500",
    "/pr-safety":         "bg-rose-500",
    "/agent-packs":       "bg-cyan-500",
    "/agent-generator":   "bg-green-500",
    "/skills-generator":  "bg-yellow-500",
};

const accentRingMap: Record<string, string> = {
    "/":                  "ring-blue-500/30",
    "/optimizer":         "ring-emerald-500/30",
    "/offline":           "ring-zinc-500/30",
    "/benchmark":         "ring-amber-500/30",
    "/pr-safety":         "ring-rose-500/30",
    "/agent-packs":       "ring-cyan-500/30",
    "/agent-generator":   "ring-green-500/30",
    "/skills-generator":  "ring-yellow-500/30",
};

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-16 md:w-20 h-screen bg-black/20 border-r border-white/5 flex flex-col items-center py-6 gap-6 backdrop-blur-md z-50">
            <div className="h-10 w-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20 mb-4">
                P
            </div>

            <nav className="flex flex-col items-center gap-6 flex-1" aria-label="Main">
            {navItems.map((item) => {
                const isActive = pathname === item.path;
                const accentBar = accentBarMap[item.path] ?? "bg-blue-500";
                const accentRing = accentRingMap[item.path] ?? "ring-white/20";

                return (
                    <Link
                        key={item.path}
                        href={item.path}
                        className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 relative group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                            isActive
                                ? `bg-white/[0.08] text-white shadow-lg shadow-white/5 ring-1 ${accentRing}`
                                : "text-zinc-500 hover:text-white hover:bg-white/5"
                        }`}
                        aria-label={item.name}
                        aria-current={isActive ? "page" : undefined}
                    >
                        <item.Icon size={20} strokeWidth={1.75} aria-hidden="true" />

                        {isActive && (
                            <div className={`animate-slide-in absolute left-[-2px] top-2 bottom-2 w-1 ${accentBar} rounded-full`} />
                        )}

                        {/* Tooltip */}
                        <div className="absolute left-14 bg-zinc-900 border border-white/10 px-2 py-1 rounded text-xs text-zinc-200 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                            {item.name}
                        </div>
                    </Link>
                );
            })}
            </nav>

            <div
                className="flex flex-col items-center gap-3 border-t border-white/5 pt-4 w-full"
                aria-label="Use it in your editor or repo"
            >
                {outboundLinks.map((item) => (
                    <a
                        key={item.href}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 relative group text-zinc-500 hover:text-white hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                        aria-label={item.name}
                    >
                        <item.Icon size={18} strokeWidth={1.75} aria-hidden="true" />

                        <div className="absolute left-14 bg-zinc-900 border border-white/10 px-2 py-1 rounded text-xs text-zinc-200 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                            {item.name}
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
}
