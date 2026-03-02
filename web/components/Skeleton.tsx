"use client";

/** Animated skeleton placeholder for a loading result section. */
export function SectionSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-3 py-2">
      <div className="h-5 w-40 rounded bg-gray-200 dark:bg-gray-700" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="rounded border border-gray-100 p-3 space-y-2 dark:border-gray-700">
          <div
            className="h-4 rounded bg-gray-200 dark:bg-gray-700"
            style={{ width: `${62 + (i % 3) * 11}%` }}
          />
          <div
            className="h-3 rounded bg-gray-100 dark:bg-gray-700/70"
            style={{ width: `${44 + (i % 2) * 18}%` }}
          />
          <div className="h-3 w-28 rounded bg-gray-100 dark:bg-gray-700/70" />
        </div>
      ))}
    </div>
  );
}
