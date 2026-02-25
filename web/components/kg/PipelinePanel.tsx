"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchPipelineStatus,
  triggerPipeline,
  fetchPipelineHistory,
  type PipelineStatus,
} from "@/lib/api";
import type { PipelineRun } from "@/lib/types";

export function PipelinePanel() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [history, setHistory] = useState<PipelineRun[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const mountedRef = useRef(true);
  useEffect(() => { return () => { mountedRef.current = false; }; }, []);

  const load = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([
        fetchPipelineStatus(),
        fetchPipelineHistory(5),
      ]);
      setStatus(s);
      setHistory(h);
    } catch {
      // silently ignore — panel is informational
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggered(false);
    try {
      await triggerPipeline();
      setTriggered(true);
      setTimeout(() => setTriggered(false), 3000);
      // Reload status after a short delay
      setTimeout(() => { if (mountedRef.current) load(); }, 2000);
    } catch {
      // ignore
    } finally {
      setTriggering(false);
    }
  };

  const fmtTime = (iso: string | null) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const fmtDuration = (s: number | null) => {
    if (s == null) return "—";
    if (s < 60) return `${Math.round(s)}s`;
    return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Pipeline Status
        </h3>
        <div className="flex items-center gap-2">
          {triggered && (
            <span className="text-xs text-green-600 font-medium">Triggered</span>
          )}
          <button
            type="button"
            onClick={handleTrigger}
            disabled={triggering || status?.state === "running"}
            className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-50"
          >
            {triggering ? "Starting…" : status?.state === "running" ? "Running…" : "Run Now"}
          </button>
        </div>
      </div>

      {status ? (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-slate-400 text-xs">State</span>
            <p className="font-medium text-slate-800 flex items-center gap-1.5">
              <span className={`inline-block h-2 w-2 rounded-full ${status.state === "running" ? "bg-amber-400 animate-pulse" : "bg-green-400"}`} />
              {status.state === "running" ? "Running" : "Idle"}
            </p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Runs completed</span>
            <p className="font-medium text-slate-800 tabular-nums">{status.runs_completed}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Last run</span>
            <p className="font-medium text-slate-800">{fmtTime(status.last_run)}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Next run</span>
            <p className="font-medium text-slate-800">
              {status.next_run_in_minutes != null
                ? `in ${Math.round(status.next_run_in_minutes)}m`
                : fmtTime(status.next_run)}
            </p>
          </div>
          {status.last_new_papers != null && (
            <div>
              <span className="text-slate-400 text-xs">Last papers</span>
              <p className="font-medium text-slate-800 tabular-nums">+{status.last_new_papers}</p>
            </div>
          )}
          {status.last_valid_triples != null && (
            <div>
              <span className="text-slate-400 text-xs">Last triples</span>
              <p className="font-medium text-slate-800 tabular-nums">+{status.last_valid_triples}</p>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-400">Loading pipeline status…</p>
      )}

      {/* Recent runs */}
      {history.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
            Recent Runs
          </h4>
          <div className="space-y-1.5">
            {history.map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between text-xs text-slate-600"
              >
                <div className="flex items-center gap-2">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                    run.state === "completed" ? "bg-green-400" :
                    run.state === "running" ? "bg-amber-400 animate-pulse" :
                    "bg-red-400"
                  }`} />
                  <span className="font-mono text-slate-500">#{run.id}</span>
                </div>
                <div className="flex items-center gap-3 tabular-nums">
                  <span>+{run.new_papers ?? 0} papers</span>
                  <span>+{run.valid_triples ?? 0} triples</span>
                  <span className="text-slate-400">{fmtDuration(run.elapsed_s)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
