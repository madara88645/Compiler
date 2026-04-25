import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ContextManager from "../ContextManager";

const useContextManagerMock = vi.fn();

vi.mock("../../hooks/useContextManager", () => ({
    useContextManager: () => useContextManagerMock(),
}));

describe("ContextManager", () => {
    it("renders hook-driven status, stats, and safe ingest action", () => {
        useContextManagerMock.mockReturnValue({
            ingesting: false,
            searching: false,
            query: "compiler",
            setQuery: vi.fn(),
            results: [],
            filePath: "",
            setFilePath: vi.fn(),
            status: "Indexed 2/2 files (8 chunks)",
            isConnected: true,
            indexStats: { docs: 2, chunks: 8, total_bytes: 4096 },
            uploadProgress: null,
            uploadFiles: vi.fn(),
            ingestPath: vi.fn(),
            runSearch: vi.fn(),
        });

        render(
            <ContextManager
                onInsertContext={vi.fn()}
                suggestions={[
                    {
                        path: "src/compiler.ts",
                        name: "compiler.ts",
                        reason: "Core compile path",
                    },
                ]}
            />,
        );

        expect(screen.getByText("Context Manager")).toBeTruthy();
        expect(screen.getByText("Connected")).toBeTruthy();
        expect(screen.getByText("2")).toBeTruthy();
        expect(screen.getByText("4.0 KB")).toBeTruthy();
        expect(screen.getByText("Indexed 2/2 files (8 chunks)")).toBeTruthy();

        const ingestButton = screen.getByRole("button", {
            name: "Ingest Path",
        });
        expect(ingestButton.getAttribute("type")).toBe("button");
        expect(ingestButton.hasAttribute("disabled")).toBe(true);
    });
});
