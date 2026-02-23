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
