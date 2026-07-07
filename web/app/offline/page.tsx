"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * The standalone "Offline Compiler" surface used to claim it was "local-only"
 * and "requires no API keys" — but it called the same backend over the
 * network as the main Compiler page; the only difference was `v2: false`
 * (skip the LLM call, stay on the deterministic heuristic pipeline).
 *
 * That engine choice now lives on the main Compiler page as a "Heuristics
 * only (no LLM)" toggle next to Conservative mode, so this route just sends
 * visitors (and old bookmarks/links) there instead of duplicating the page.
 */
export default function OfflinePage() {
    const router = useRouter();

    useEffect(() => {
        router.replace("/");
    }, [router]);

    return (
        <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center text-zinc-400">
            <p className="max-w-md text-sm leading-relaxed">
                The Offline Compiler has moved. Use the &quot;Heuristics only (no LLM)&quot; engine
                toggle on the main Compiler page instead.
            </p>
            <a
                href="/"
                className="text-sm font-medium text-blue-400 underline underline-offset-2 hover:text-blue-300"
            >
                Go to the Compiler
            </a>
        </main>
    );
}
