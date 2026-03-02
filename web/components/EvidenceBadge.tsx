"use client";

import type { Evidence } from "@/lib/types";

/**
 * Trust badge: Information = blue, Knowledge = green, Wisdom = gold (per project rules).
 * source_type PMC = single source (info); FDA/drug_label = trusted (knowledge); recommendation = wisdom (gold).
 */
export function EvidenceBadge({
  evidence,
  variant = "info",
}: {
  evidence: Evidence;
  variant?: "info" | "knowledge" | "wisdom";
}) {
  const label =
    variant === "wisdom"
      ? "Wisdom"
      : variant === "knowledge"
        ? "Knowledge"
        : "Information";
  const bg =
    variant === "wisdom"
      ? "bg-amber-400 text-amber-900"
      : variant === "knowledge"
        ? "bg-green-500 text-white"
        : "bg-blue-500 text-white";

  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${bg}`}
      title={`${evidence.source_type} ${evidence.source_id} ${evidence.journal} ${evidence.pub_date}`}
    >
      {label}
      {evidence.source_type && (
        <span className="ml-1 opacity-90">({evidence.source_type})</span>
      )}
    </span>
  );
}

/** Compact legend explaining the blue / green / gold badge system. */
export function EvidenceLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
      <span className="font-medium text-gray-700">Evidence level:</span>
      <span className="flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-blue-500" />
        <strong>Information</strong>
        <span className="text-gray-400">— raw evidence, single source</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-green-500" />
        <strong>Knowledge</strong>
        <span className="text-gray-400">— KG-backed, may be multi-source</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-amber-400" />
        <strong>Wisdom</strong>
        <span className="text-gray-400">— actionable recommendation</span>
      </span>
    </div>
  );
}

export function EvidenceList({
  evidenceList,
  variant = "info",
}: {
  evidenceList: Evidence[];
  variant?: "info" | "knowledge" | "wisdom";
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {evidenceList.map((ev, i) => (
        <EvidenceBadge key={i} evidence={ev} variant={variant} />
      ))}
    </div>
  );
}
