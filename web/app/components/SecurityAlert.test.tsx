import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import SecurityAlert from "./SecurityAlert";
import type { SecurityFinding } from "../../lib/api/types";

const findings: SecurityFinding[] = [
    { type: "openai_key", original: "sk-live-abc123", masked: "sk-live-***" },
];

describe("SecurityAlert", () => {
    test("calls onCancel when Escape is pressed", () => {
        const onCancel = vi.fn();
        render(
            <SecurityAlert
                findings={findings}
                redactedText="redacted preview"
                onProceedRedacted={vi.fn()}
                onProceedOriginal={vi.fn()}
                onCancel={onCancel}
            />
        );

        fireEvent.keyDown(document, { key: "Escape" });

        expect(onCancel).toHaveBeenCalledTimes(1);
    });

    test("calls onCancel when the backdrop is clicked", () => {
        const onCancel = vi.fn();
        render(
            <SecurityAlert
                findings={findings}
                redactedText="redacted preview"
                onProceedRedacted={vi.fn()}
                onProceedOriginal={vi.fn()}
                onCancel={onCancel}
            />
        );

        const dialog = screen.getByRole("dialog");
        // The backdrop is the dialog's parent element.
        fireEvent.click(dialog.parentElement as HTMLElement);

        expect(onCancel).toHaveBeenCalledTimes(1);
    });

    test("does not call onCancel when clicking inside the dialog", () => {
        const onCancel = vi.fn();
        render(
            <SecurityAlert
                findings={findings}
                redactedText="redacted preview"
                onProceedRedacted={vi.fn()}
                onProceedOriginal={vi.fn()}
                onCancel={onCancel}
            />
        );

        fireEvent.click(screen.getByRole("dialog"));

        expect(onCancel).not.toHaveBeenCalled();
    });

    test("keeps Tab focus contained within the modal", () => {
        const onCancel = vi.fn();
        render(
            <SecurityAlert
                findings={findings}
                redactedText="redacted preview"
                onProceedRedacted={vi.fn()}
                onProceedOriginal={vi.fn()}
                onCancel={onCancel}
            />
        );

        const cancelButton = screen.getByRole("button", { name: "Cancel" });
        const stripButton = screen.getByRole("button", { name: /Strip Secrets & Proceed/i });

        stripButton.focus();
        expect(document.activeElement).toBe(stripButton);

        fireEvent.keyDown(document, { key: "Tab" });
        expect(document.activeElement).toBe(cancelButton);

        fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
        expect(document.activeElement).toBe(stripButton);
    });
});
