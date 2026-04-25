import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import FileUploadZone from "../context/FileUploadZone";

describe("FileUploadZone", () => {
    it("uses non-submit buttons for upload actions", () => {
        const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());

        render(
            <form onSubmit={onSubmit}>
                <FileUploadZone
                    ingesting={false}
                    uploadProgress={null}
                    onUploadFiles={vi.fn().mockResolvedValue(undefined)}
                />
            </form>,
        );

        const uploadFilesButton = screen.getByRole("button", {
            name: "Upload Files",
        });
        const uploadFolderButton = screen.getByRole("button", {
            name: "Upload Folder",
        });

        fireEvent.click(uploadFilesButton);
        fireEvent.click(uploadFolderButton);

        expect(uploadFilesButton.getAttribute("type")).toBe("button");
        expect(uploadFolderButton.getAttribute("type")).toBe("button");
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it("uploads dropped files and shows progress state", async () => {
        const onUploadFiles = vi.fn().mockResolvedValue(undefined);
        const file = new File(["hello"], "notes.md", { type: "text/markdown" });
        const { rerender, container } = render(
            <FileUploadZone
                ingesting={false}
                uploadProgress={null}
                onUploadFiles={onUploadFiles}
            />,
        );

        fireEvent.drop(container.firstChild as HTMLElement, {
            dataTransfer: {
                files: [file],
            },
        });

        expect(onUploadFiles).toHaveBeenCalledWith([file]);

        rerender(
            <FileUploadZone
                ingesting={true}
                uploadProgress={{
                    completed: 0,
                    currentFile: "notes.md",
                    total: 1,
                }}
                onUploadFiles={onUploadFiles}
            />,
        );

        expect(screen.getByText("Uploading context")).toBeTruthy();
        expect(screen.getByText("notes.md")).toBeTruthy();
    });
});
