import { Skeleton, SkeletonBlock } from "./Skeleton";

export default function OutputSkeleton() {
    return (
        <div className="flex flex-col h-full animate-fade-in">
            {/* Tab bar skeleton */}
            <div className="flex gap-2 px-4 pt-4 pb-2 border-b border-white/5">
                {["w-16", "w-20", "w-14", "w-18", "w-22", "w-12", "w-18"].map(
                    (w, i) => (
                        <Skeleton key={i} className={`h-8 ${w}`} />
                    ),
                )}
            </div>

            {/* Content skeleton */}
            <div className="flex-1 p-6 space-y-6">
                {/* Title block */}
                <div className="space-y-2">
                    <Skeleton className="h-5 w-[45%]" />
                    <Skeleton className="h-3 w-[30%]" />
                </div>

                {/* Body block */}
                <SkeletonBlock lines={6} />

                {/* Second section */}
                <div className="pt-4 space-y-2">
                    <Skeleton className="h-5 w-[35%]" />
                </div>
                <SkeletonBlock lines={4} />
            </div>
        </div>
    );
}
