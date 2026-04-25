import type { UploadProgress } from "../../hooks/useContextManager";

type UploadProgressCardProps = {
    uploadProgress: UploadProgress;
};

export default function UploadProgressCard({ uploadProgress }: UploadProgressCardProps) {
    const uploadPercent = Math.max(
        8,
        Math.min(
            100,
            Math.round(
                ((uploadProgress.completed + (uploadProgress.currentFile ? 0.45 : 0)) / uploadProgress.total) * 100,
            ),
        ),
    );
    const currentStep = Math.min(
        uploadProgress.total,
        uploadProgress.completed + (uploadProgress.currentFile ? 1 : 0),
    );

    return (
        <div className="w-full max-w-sm rounded-2xl border border-cyan-400/20 bg-cyan-500/[0.08] p-4 shadow-[0_0_40px_rgba(34,211,238,0.08)]">
            <div className="flex items-start gap-3">
                <span className="mt-1 relative flex h-3 w-3 shrink-0">
                    <span className="absolute inline-flex h-full w-full rounded-full bg-cyan-300/30 animate-ping" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-cyan-300" />
                </span>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-cyan-100">Uploading context</span>
                        <span className="text-xs font-mono text-cyan-200/80">
                            {currentStep}/{uploadProgress.total}
                        </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-cyan-100/70">
                        {uploadProgress.currentFile ? uploadProgress.currentFile : "Preparing files..."}
                    </p>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/20">
                        <div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-400 transition-[width] duration-500"
                            style={{ width: `${uploadPercent}%` }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
