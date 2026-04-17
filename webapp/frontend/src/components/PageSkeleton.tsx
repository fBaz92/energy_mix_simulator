/**
 * Lightweight page-level loading placeholder.
 * Used as the Suspense fallback while lazy routes load.
 */
export function PageSkeleton() {
  return (
    <div className="p-8 space-y-4 animate-pulse">
      <div className="h-7 w-48 rounded bg-muted" />
      <div className="h-4 w-80 rounded bg-muted/60" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-24 rounded-xl border bg-card" />
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-72 rounded-xl border bg-card" />
        ))}
      </div>
    </div>
  );
}
