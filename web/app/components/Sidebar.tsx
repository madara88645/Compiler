"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
    Blocks,
    Bot,
    Code2,
    FolderArchive,
    FolderKanban,
    Github,
    Plug,
    ShieldCheck,
    Sparkles,
    Swords,
    Terminal,
    type LucideIcon,
    Zap,
} from "lucide-react";

type NavItem = {
    name: string;
    path: string;
    Icon: LucideIcon;
    activePaths?: readonly string[];
};
type NavGroup = { label: string; items: NavItem[] };

// Compiler is intentionally first: it is the primary, always-on entry point.
const navGroups: NavGroup[] = [
    {
        label: "Prompt tools",
        items: [
            { name: "Compiler",       path: "/",          Icon: Code2    },
            { name: "Token Optimizer", path: "/optimizer", Icon: Sparkles },
            { name: "Benchmark", path: "/benchmark", Icon: Swords },
        ],
    },
    {
        label: "Repo checks",
        items: [
            { name: "PR Safety", path: "/pr-safety", Icon: ShieldCheck },
        ],
    },
];

const agenticCodingItems: NavItem[] = [
    {
        name: "Projects",
        path: "/agentic-coding",
        activePaths: ["/agent-packs", "/agentic-coding/projects/export", "/agentic-coding/instructions"],
        Icon: FolderArchive,
    },
    {
        name: "Agent Generator",
        path: "/agentic-coding/agents",
        activePaths: ["/agent-generator"],
        Icon: Bot,
    },
    {
        name: "Skill Generator",
        path: "/agentic-coding/skills",
        activePaths: ["/skills-generator"],
        Icon: Zap,
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
        href: "https://github.com/madara88645/Compiler/blob/main/integrations/vscode-extension/README.md#install",
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
    "/agentic-coding":       "bg-cyan-500",
    "/agentic-coding/agents": "bg-green-500",
    "/agentic-coding/skills": "bg-yellow-500",
};

const accentRingMap: Record<string, string> = {
    "/":                  "ring-blue-500/30",
    "/optimizer":         "ring-emerald-500/30",
    "/benchmark":         "ring-amber-500/30",
    "/pr-safety":         "ring-rose-500/30",
    "/agentic-coding":       "ring-cyan-500/30",
    "/agentic-coding/agents": "ring-green-500/30",
    "/agentic-coding/skills": "ring-yellow-500/30",
};

function isNavItemActive(item: NavItem, pathname: string): boolean {
    return item.path === pathname || item.activePaths?.includes(pathname) === true;
}

function isAgenticCodingPath(pathname: string | null): boolean {
    if (!pathname) return false;

    const agenticRoot = "/agentic-coding";
    const legacyRoots = ["/agent-packs", "/agent-generator", "/skills-generator"];
    return (
        pathname === agenticRoot ||
        pathname.startsWith(`${agenticRoot}/`) ||
        legacyRoots.some((root) => pathname === root || pathname.startsWith(`${root}/`))
    );
}

export default function Sidebar() {
    const pathname = usePathname();
    const agenticCodingActive = isAgenticCodingPath(pathname);
    const [agenticCodingOpen, setAgenticCodingOpen] = useState(agenticCodingActive);

    useEffect(() => {
        if (agenticCodingActive) {
            queueMicrotask(() => setAgenticCodingOpen(true));
        }
    }, [agenticCodingActive]);

    const renderNavItem = (item: NavItem) => {
        const isActive = pathname ? isNavItemActive(item, pathname) : false;
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
                    className="hidden md:block max-w-full whitespace-normal break-words text-center text-[9px] font-medium leading-tight tracking-tight"
                    aria-hidden="true"
                >
                    {item.name}
                </span>

                {isActive && (
                    <div className={`animate-slide-in absolute left-[-2px] top-2 bottom-2 w-1 ${accentBar} rounded-full`} />
                )}
            </Link>
        );
    };

    const renderNavGroup = (group: NavGroup, showSeparator: boolean) => (
        <div key={group.label} className="w-full flex flex-col items-center">
            {showSeparator && (
                <div
                    role="separator"
                    aria-orientation="horizontal"
                    className="w-8 h-px bg-white/10 my-3 shrink-0"
                />
            )}

            <span
                className="hidden md:block mb-1 max-w-16 text-center text-[8px] font-semibold uppercase leading-tight tracking-[0.12em] text-zinc-500"
                aria-hidden="true"
                title={group.label}
            >
                {group.label}
            </span>

            <div
                role="group"
                aria-label={group.label}
                className="flex flex-col items-center gap-2 w-full"
            >
                {group.items.map(renderNavItem)}
            </div>
        </div>
    );

    return (
        <div className="w-16 md:w-24 h-screen bg-black/20 border-r border-white/5 flex flex-col items-center py-6 gap-1 backdrop-blur-md z-50 overflow-y-auto overflow-x-hidden">
            <div className="h-10 w-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20 mb-4 shrink-0">
                P
            </div>

            {renderNavGroup(navGroups[0], false)}

            <div className="w-full flex flex-col items-center">
                <div
                    role="separator"
                    aria-orientation="horizontal"
                    className="w-8 h-px bg-white/10 my-3 shrink-0"
                />

                <button
                    type="button"
                    className={`w-12 md:w-16 py-2 rounded-xl flex flex-col items-center justify-center gap-1 transition-all duration-300 relative group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                        agenticCodingActive
                            ? "bg-white/[0.08] text-white shadow-lg shadow-white/5 ring-1 ring-cyan-500/30"
                            : "text-zinc-500 hover:text-white hover:bg-white/5"
                    }`}
                    aria-label="Agentic Coding"
                    aria-expanded={agenticCodingOpen}
                    aria-controls="agentic-coding-navigation"
                    title="Agentic Coding"
                    onClick={() => setAgenticCodingOpen((open) => !open)}
                >
                    <FolderKanban size={20} strokeWidth={1.75} aria-hidden="true" />
                    <span
                        className="hidden md:block max-w-full whitespace-normal break-words text-center text-[9px] font-medium leading-tight tracking-tight"
                        aria-hidden="true"
                    >
                        Agentic Coding
                    </span>
                    {agenticCodingActive && (
                        <div className="animate-slide-in absolute left-[-2px] top-2 bottom-2 w-1 bg-cyan-500 rounded-full" />
                    )}
                </button>

                <div
                    id="agentic-coding-navigation"
                    role="group"
                    aria-label="Agentic Coding"
                    hidden={!agenticCodingOpen}
                    className="flex flex-col items-center gap-2 w-full"
                >
                    {agenticCodingOpen && agenticCodingItems.map(renderNavItem)}
                </div>
            </div>

            {renderNavGroup(navGroups[1], true)}

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
                        <span
                            className="absolute left-full ml-4 z-[60] bg-zinc-800 border border-white/10 text-zinc-100 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-all duration-200 shadow-xl pointer-events-none -translate-x-2 group-hover:translate-x-0"
                            aria-hidden="true"
                        >
                            {item.name}
                        </span>
                        <item.Icon size={18} strokeWidth={1.75} aria-hidden="true" />
                    </a>
                ))}
            </div>
        </div>
    );
}
