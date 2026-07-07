"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Code2, Sparkles, Swords, Bot, Zap, FolderArchive, ShieldCheck, Github, Terminal, Blocks, Plug, type LucideIcon } from "lucide-react";

type NavItem = { name: string; path: string; Icon: LucideIcon };
type NavGroup = { label: string; items: NavItem[] };

// Compiler is intentionally first: it is the primary, always-on entry point.
const navGroups: NavGroup[] = [
    {
        label: "Compile",
        items: [
            { name: "Compiler",  path: "/",         Icon: Code2    },
            { name: "Optimizer", path: "/optimizer", Icon: Sparkles },
        ],
    },
    {
        label: "Prove",
        items: [
            { name: "Benchmark", path: "/benchmark", Icon: Swords },
        ],
    },
    {
        label: "Ship agent assets",
        items: [
            { name: "Agent Packs",      path: "/agent-packs",      Icon: FolderArchive },
            { name: "Agent Generator",  path: "/agent-generator",  Icon: Bot           },
            { name: "Skills Generator", path: "/skills-generator", Icon: Zap           },
        ],
    },
    {
        label: "Repo checks",
        items: [
            { name: "PR Safety", path: "/pr-safety", Icon: ShieldCheck },
        ],
    },
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
    "/benchmark":         "bg-amber-500",
    "/pr-safety":         "bg-rose-500",
    "/agent-packs":       "bg-cyan-500",
    "/agent-generator":   "bg-green-500",
    "/skills-generator":  "bg-yellow-500",
};

const accentRingMap: Record<string, string> = {
    "/":                  "ring-blue-500/30",
    "/optimizer":         "ring-emerald-500/30",
    "/benchmark":         "ring-amber-500/30",
    "/pr-safety":         "ring-rose-500/30",
    "/agent-packs":       "ring-cyan-500/30",
    "/agent-generator":   "ring-green-500/30",
    "/skills-generator":  "ring-yellow-500/30",
};

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-16 md:w-24 h-screen bg-black/20 border-r border-white/5 flex flex-col items-center py-6 gap-1 backdrop-blur-md z-50 overflow-y-auto">
            <div className="h-10 w-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20 mb-4 shrink-0">
                P
            </div>

            {navGroups.map((group, groupIndex) => (
                <div key={group.label} className="w-full flex flex-col items-center">
                    {groupIndex > 0 && (
                        <div
                            role="separator"
                            aria-orientation="horizontal"
                            className="w-8 h-px bg-white/10 my-3 shrink-0"
                        />
                    )}

                    <div
                        role="group"
                        aria-label={group.label}
                        className="flex flex-col items-center gap-2 w-full"
                    >
                        {group.items.map((item) => {
                            const isActive = pathname === item.path;
                            const accentBar = accentBarMap[item.path] ?? "bg-blue-500";
                            const accentRing = accentRingMap[item.path] ?? "ring-white/20";

                            return (
                                <Link
                                    key={item.path}
                                    href={item.path}
                                    className={`w-12 md:w-16 py-2 rounded-xl flex flex-col items-center justify-center gap-1 transition-all duration-300 relative group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                                        isActive
                                            ? `bg-white/[0.08] text-white shadow-lg shadow-white/5 ring-1 ${accentRing}`
                                            : "text-zinc-500 hover:text-white hover:bg-white/5"
                                    }`}
                                    aria-label={item.name}
                                    aria-current={isActive ? "page" : undefined}
                                >
                                    <item.Icon size={20} strokeWidth={1.75} aria-hidden="true" />

                                    <span
                                        className="hidden md:block text-[9px] leading-none font-medium tracking-tight text-center truncate max-w-full"
                                        aria-hidden="true"
                                    >
                                        {item.name}
                                    </span>

                                    {isActive && (
                                        <div className={`animate-slide-in absolute left-[-2px] top-2 bottom-2 w-1 ${accentBar} rounded-full`} />
                                    )}

                                    {/* Tooltip */}
                                    <div className="absolute left-full ml-2 bg-zinc-900 border border-white/10 px-2 py-1 rounded text-xs text-zinc-200 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                                        {item.name}
                                    </div>
                                </Link>
                            );
                        })}
                    </div>
                </div>
            ))}

            <div
                className="mt-auto flex flex-col items-center gap-3 border-t border-white/5 pt-4 w-full"
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

                        <div className="absolute left-full ml-2 bg-zinc-900 border border-white/10 px-2 py-1 rounded text-xs text-zinc-200 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                            {item.name}
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
}
