import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OfflinePage from "../offline/page";
import { apiFetch } from "@/config";
import { compilePrompt } from "../../lib/api/promptc";

vi.mock("@/config", () => ({
    apiFetch: vi.fn(),
    describeRequestError: (error: unknown) =>
        error instanceof Error ? error.message : "Connection failed.",
}));

vi.mock("../../lib/api/promptc", () => ({
    compilePrompt: vi.fn(),
}));

vi.mock("../components/ContextManager", () => ({
    default: () => <div data-testid="context-manager" />,
}));

vi.mock("../components/InfoButton", () => ({
    default: ({ title }: { title: string }) => (
        <button type="button">{title}</button>
    ),
}));

const apiFetchMock = vi.mocked(apiFetch);
const compilePromptMock = vi.mocked(compilePrompt);

describe("Offline compiler page", () => {
    beforeEach(() => {
        apiFetchMock.mockReset();
        compilePromptMock.mockReset();
        apiFetchMock.mockRejectedValue(
            new Error("Offline backend unavailable"),
        );
        compilePromptMock.mockRejectedValue(
            new Error("Offline backend unavailable"),
        );
    });

    it("keeps failed offline compiles visible and retryable", async () => {
        render(<OfflinePage />);

        fireEvent.change(screen.getByLabelText("Offline prompt input"), {
            target: { value: "Summarize this incident report." },
        });
        fireEvent.click(
            screen.getByRole("button", { name: /Run Heuristics/i }),
        );

        expect(
            await screen.findByText("Error: Offline backend unavailable"),
        ).toBeTruthy();

        fireEvent.click(
            screen.getByRole("button", { name: "Retry offline compile" }),
        );

        await waitFor(() => {
            expect(compilePromptMock).toHaveBeenCalledTimes(2);
        });
    });
});
