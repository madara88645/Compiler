"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Sidebar() {
    const pathname = usePathname();

    const navItems = [
        { name: "Compiler", path: "/", icon: "💠" },
        { name: "Optimizer", path: "/optimizer", icon: "✨" },
        { name: "Offline", path: "/offline", icon: "🔌" },
        { name: "Benchmark", path: "/benchmark", icon: "⚔️" },
        { name: "Agent Generator", path: "/agent-generator", icon: "🧠" },
        { name: "Skills Generator", path: "/skills-generator", icon: "⚡" },
    ];

    return (
        <div className="w-16 md:w-20 h-screen bg-black/20 border-r border-white/5 flex flex-col items-center py-6 gap-6 backdrop-blur-md z-50">
            <div className="h-10 w-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20 mb-4">
                P
            </div>

            {navItems.map((item) => {
                const isActive = pathname === item.path;
                return (
                    <Link
                        key={item.path}
                        href={item.path}
                        className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg transition-all duration-300 relative group ${isActive
                            ? "bg-white/10 text-white shadow-lg shadow-white/5 ring-1 ring-white/20"
                            : "text-zinc-500 hover:text-white hover:bg-white/5"
                            }`}
                        title={item.name}
                    >
                        {item.icon}
                        {isActive && (
                            <div className="absolute left-[-2px] top-2 bottom-2 w-1 bg-blue-500 rounded-full" />
                        )}

                        {/* Tooltip */}
                        <div className="absolute left-14 bg-zinc-900 border border-white/10 px-2 py-1 rounded text-xs text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                            {item.name}
                        </div>
                    </Link>
                );
            })}
        </div>
    );
}
