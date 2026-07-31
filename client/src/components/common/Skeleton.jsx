export default function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={`animate-pulse rounded bg-appborder/60 dark:bg-appborder ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-app p-4">
        <Skeleton className="h-5 w-48" />
      </div>
      <div className="divide-y divide-[rgb(var(--color-border))]">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 p-4">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}
