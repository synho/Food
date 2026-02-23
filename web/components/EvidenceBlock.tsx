"use client";

import type { Evidence } from "@/lib/types";
import { EvidenceBadge } from "./EvidenceBadge";

export function EvidenceBlock({
  evidenceList,
  variant = "info",
}: {
  evidenceList: Evidence[];
  variant?: "info" | "knowledge" | "wisdom";
}) {
  if (!evidenceList?.length) return null;
  return (
    <div className="mt-1 space-y-1 text-xs text-gray-600">
      {evidenceList.map((ev, i) => (
        <div key={i} className="flex flex-wrap items-center gap-1 rounded bg-gray-50 px-2 py-1">
          <EvidenceBadge evidence={ev} variant={variant} />
          {ev.context && <span className="flex-1">{ev.context}</span>}
          {(ev.journal || ev.pub_date) && (
            <span className="text-gray-400">
              {ev.journal} {ev.pub_date}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
