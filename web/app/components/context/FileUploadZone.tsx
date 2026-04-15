"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import type { UploadProgress } from "../../hooks/useContextManager";
import UploadProgressCard from "./UploadProgressCard";

type FileUploadZoneProps = {
    ingesting: boolean;
    uploadProgress: UploadProgress | null;
    onUploadFiles: (files: File[]) => Promise<void>;
};

export default function FileUploadZone({ ingesting, uploadProgress, onUploadFiles }: FileUploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const directoryInputRef = useRef<HTMLInputElement>(null);

    const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            await onUploadFiles(files);
        }
    };

    const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        await onUploadFiles(Array.from(files));
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleDirectorySelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;
        await onUploadFiles(Array.from(files));
        if (directoryInputRef.current) directoryInputRef.current.value = "";
    };

    return (
        <div
            onDrop={handleDrop}
            onDragOver={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragging(false); }}
            className={`
                relative flex flex-col items-center justify-center gap-2 p-4
                border-2 border-dashed rounded-xl
                transition-all duration-200
                ${isDragging ? "border-blue-500 bg-blue-500/10 scale-[1.02]" : "border-white/10 bg-white/[0.02]"}
                ${ingesting ? "pointer-events-none opacity-50" : ""}
            `}
        >
            <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} className="hidden" />
            <input
                ref={directoryInputRef}
                type="file"
                multiple
                // @ts-expect-error - webkitdirectory is not in standard types but supported by browsers
                webkitdirectory=""
                directory=""
                onChange={handleDirectorySelect}
                className="hidden"
            />

            {ingesting && uploadProgress ? (
                <UploadProgressCard uploadProgress={uploadProgress} />
            ) : (
                <>
                    <div className={`text-2xl ${isDragging ? "scale-110" : ""} transition-transform`}>Files</div>
                    <div className="flex gap-2">
                        <button type="button" onClick={() => fileInputRef.current?.click()} className="text-xs text-blue-400 font-medium hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                            Upload Files
                        </button>
                        <span className="text-xs text-zinc-500">|</span>
                        <button type="button" onClick={() => directoryInputRef.current?.click()} className="text-xs text-blue-400 font-medium hover:text-blue-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                            Upload Folder
                        </button>
                    </div>
                    <div className="text-[10px] text-zinc-600 mt-1">Or drag and drop project context</div>
                </>
            )}
        </div>
    );
}
