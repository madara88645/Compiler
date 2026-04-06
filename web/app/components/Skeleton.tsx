export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SkeletonBlock({ lines = 5 }: { lines?: number }) {
  const widths = ["w-full", "w-[85%]", "w-[92%]", "w-[78%]", "w-[88%]", "w-full", "w-[70%]"];
  return (
    <div className="space-y-3">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          className={`h-3 ${widths[i % widths.length]}`}
        />
      ))}
    </div>
  );
}
