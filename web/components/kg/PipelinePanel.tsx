"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchPipelineStatus,
  triggerPipeline,
  fetchPipelineHistory,
  fetchKgLive,
  type PipelineStatus,
  type KgLive,
} from "@/lib/api";
import type { PipelineRun } from "@/lib/types";

const PROCESS_ICONS: Record<string, string> = {
  run_expansion: "▶",
  run_overnight: "▶",
  watch_kg: "↻",
  run_pipeline: "⟳",
  fetch_papers: "↓",
  extract_triples: "⚗",
  smart_fetch: "⎯",
  ingest_to_neo4j: "⬆",
};

const PROCESS_LABELS: Record<string, string> = {
  run_expansion: "Expansion orchestrator",
  run_overnight: "Overnight orchestrator",
  watch_kg: "Watch loop",
  run_pipeline: "Pipeline runner",
  fetch_papers: "Fetching papers",
  extract_triples: "Extracting triples",
  smart_fetch: "Gap-targeted fetch",
  ingest_to_neo4j: "Ingesting to Neo4j",
};

export function PipelinePanel() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [history, setHistory] = useState<PipelineRun[]>([]);
  const [live, setLive] = useState<KgLive | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const mountedRef = useRef(true);
  useEffect(() => { return () => { mountedRef.current = false; }; }, []);

  const load = useCallback(async () => {
    try {
      const [s, h, l] = await Promise.all([
        fetchPipelineStatus().catch(() => null),
        fetchPipelineHistory(5).catch(() => []),
        fetchKgLive().catch(() => null),
      ]);
      if (s) setStatus(s);
      setHistory(h);
      if (l) setLive(l);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, live?.active ? 10_000 : 30_000);
    return () => clearInterval(id);
  }, [load, live?.active]);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggered(false);
    try {
      await triggerPipeline();
      setTriggered(true);
      setTimeout(() => setTriggered(false), 3000);
      setTimeout(() => { if (mountedRef.current) load(); }, 2000);
    } catch { /* ignore */ } finally {
      setTriggering(false);
    }
  };

  const fmtDuration = (s: number | null) => {
    if (s == null) return "—";
    if (s < 60) return `${Math.round(s)}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
    return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  };

  const fmtElapsed = (started: string) => {
    const diff = (Date.now() - new Date(started).getTime()) / 1000;
    return fmtDuration(diff);
  };

  const isExpansionActive = live?.active ?? false;
  const corpus = live?.corpus;
  const cycles = live?.cycles ?? [];
  const processes = live?.processes ?? [];
  const lastCycle = cycles.length > 0 ? cycles[cycles.length - 1] : null;

  // Sum totals across all cycles
  const totalPapersFetched = cycles.reduce((s, c) => s + c.papers, 0);
  const totalNodesDelta = cycles.reduce((s, c) => s + c.nodes_delta, 0);
  const totalRelsDelta = cycles.reduce((s, c) => s + c.rels_delta, 0);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">
            Pipeline
          </h3>
          {isExpansionActive && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </span>
          )}
        </div>
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

      {/* ── Live Expansion Section ──────────────────────────────────────── */}
      {isExpansionActive && (
        <div className="mb-4 rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 p-4 dark:from-emerald-900/10 dark:to-teal-900/10 dark:border-emerald-800">
          {/* Elapsed */}
          {live?.started_at && (
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">
                Expansion running
              </span>
              <span className="text-xs tabular-nums text-emerald-600 dark:text-emerald-400 font-mono">
                {fmtElapsed(live.started_at)} elapsed
              </span>
            </div>
          )}

          {/* Corpus bar */}
          {corpus && corpus.raw_papers > 0 && (
            <div className="mb-3">
              <div className="flex items-center justify-between text-[11px] text-slate-600 dark:text-gray-300 mb-1">
                <span>Corpus: {corpus.raw_papers.toLocaleString()} papers</span>
                <span>
                  {corpus.extracted.toLocaleString()} extracted
                  {corpus.backlog > 0 && (
                    <span className="text-amber-600 dark:text-amber-400"> · {corpus.backlog.toLocaleString()} queued</span>
                  )}
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-200 dark:bg-gray-700 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all duration-1000"
                  style={{ width: `${Math.min(100, (corpus.extracted / corpus.raw_papers) * 100)}%` }}
                />
              </div>
            </div>
          )}

          {/* Cycle stats */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-bold tabular-nums text-slate-800 dark:text-gray-100">{cycles.length}</div>
              <div className="text-[10px] text-slate-500 dark:text-gray-400">Cycles</div>
            </div>
            <div>
              <div className="text-lg font-bold tabular-nums text-blue-600 dark:text-blue-400">
                +{totalNodesDelta.toLocaleString()}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-gray-400">New nodes</div>
            </div>
            <div>
              <div className="text-lg font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                +{totalRelsDelta.toLocaleString()}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-gray-400">New rels</div>
            </div>
          </div>

          {/* Active processes */}
          {processes.length > 0 && (
            <div className="mt-3 pt-3 border-t border-emerald-200 dark:border-emerald-800">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400 mb-1.5">
                Active processes
              </div>
              <div className="space-y-1">
                {processes.map((p) => (
                  <div key={p.pid} className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs ${
                        p.name === "fetch_papers" || p.name === "smart_fetch"
                          ? "text-amber-500 animate-pulse"
                          : p.name === "extract_triples"
                            ? "text-violet-500 animate-pulse"
                            : "text-slate-400 dark:text-gray-500"
                      }`}>
                        {PROCESS_ICONS[p.name] ?? "●"}
                      </span>
                      <span className="text-slate-700 dark:text-gray-300">
                        {PROCESS_LABELS[p.name] ?? p.name}
                      </span>
                    </div>
                    <span className="tabular-nums text-slate-400 dark:text-gray-500 font-mono text-[10px]">
                      {p.cpu}% · {p.elapsed}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Cycle History ────────────────────────────────────────────────── */}
      {cycles.length > 0 && (
        <div className={isExpansionActive ? "" : "mb-4"}>
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-gray-500 mb-2">
            Expansion Cycles
          </h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {[...cycles].reverse().map((c) => (
              <div
                key={c.cycle}
                className="flex items-center justify-between text-[11px] text-slate-600 dark:text-gray-300"
              >
                <div className="flex items-center gap-2">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                    c.papers > 0 || c.nodes_delta > 0 ? "bg-emerald-400" : "bg-slate-300 dark:bg-gray-600"
                  }`} />
                  <span className="font-mono text-slate-500 dark:text-gray-400">#{c.cycle}</span>
                  <span className="text-slate-400 dark:text-gray-500">
                    {c.time.split(" ")[1] ?? c.time}
                  </span>
                </div>
                <div className="flex items-center gap-3 tabular-nums">
                  <span className={c.papers > 0 ? "text-amber-600 dark:text-amber-400 font-medium" : ""}>
                    +{c.papers} papers
                  </span>
                  <span className={c.nodes_delta > 0 ? "text-blue-600 dark:text-blue-400 font-medium" : ""}>
                    +{c.nodes_delta} nodes
                  </span>
                  <span className={c.rels_delta > 0 ? "text-emerald-600 dark:text-emerald-400 font-medium" : ""}>
                    +{c.rels_delta} rels
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Server Pipeline Status (when no expansion) ─────────────────── */}
      {!isExpansionActive && status && (
        <div className="grid grid-cols-2 gap-3 text-sm mb-4">
          <div>
            <span className="text-slate-400 text-xs dark:text-gray-500">State</span>
            <p className="font-medium text-slate-800 flex items-center gap-1.5 dark:text-gray-100">
              <span className={`inline-block h-2 w-2 rounded-full ${status.state === "running" ? "bg-amber-400 animate-pulse" : "bg-green-400"}`} />
              {status.state === "running" ? "Running" : "Idle"}
            </p>
          </div>
          <div>
            <span className="text-slate-400 text-xs dark:text-gray-500">Completed runs</span>
            <p className="font-medium text-slate-800 tabular-nums dark:text-gray-100">{status.runs_completed}</p>
          </div>
          {status.last_new_papers != null && (
            <div>
              <span className="text-slate-400 text-xs dark:text-gray-500">Last papers</span>
              <p className="font-medium text-slate-800 tabular-nums dark:text-gray-100">+{status.last_new_papers}</p>
            </div>
          )}
          {status.last_valid_triples != null && (
            <div>
              <span className="text-slate-400 text-xs dark:text-gray-500">Last triples</span>
              <p className="font-medium text-slate-800 tabular-nums dark:text-gray-100">+{status.last_valid_triples}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Corpus Stats (always shown if available) ───────────────────── */}
      {!isExpansionActive && corpus && corpus.raw_papers > 0 && (
        <div className="mb-4 rounded-lg bg-slate-50 dark:bg-gray-700/30 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-gray-500 mb-2">
            Corpus
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <div>
              <div className="font-bold tabular-nums text-slate-800 dark:text-gray-100">{corpus.raw_papers.toLocaleString()}</div>
              <div className="text-[10px] text-slate-400 dark:text-gray-500">Papers</div>
            </div>
            <div>
              <div className="font-bold tabular-nums text-slate-800 dark:text-gray-100">{corpus.extracted.toLocaleString()}</div>
              <div className="text-[10px] text-slate-400 dark:text-gray-500">Extracted</div>
            </div>
            <div>
              <div className={`font-bold tabular-nums ${corpus.backlog > 0 ? "text-amber-600 dark:text-amber-400" : "text-slate-800 dark:text-gray-100"}`}>
                {corpus.backlog.toLocaleString()}
              </div>
              <div className="text-[10px] text-slate-400 dark:text-gray-500">Backlog</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Recent Pipeline Runs ──────────────────────────────────────── */}
      {history.length > 0 && (
        <div className="border-t border-slate-100 pt-3 dark:border-gray-700">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2 dark:text-gray-500">
            Recent Runs
          </h4>
          <div className="space-y-1.5">
            {history.map((run) => (
              <div
                key={run.id}
                className="flex items-center justify-between text-xs text-slate-600 dark:text-gray-300"
              >
                <div className="flex items-center gap-2">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                    run.state === "completed" ? "bg-green-400" :
                    run.state === "running" ? "bg-amber-400 animate-pulse" :
                    "bg-red-400"
                  }`} />
                  <span className="font-mono text-slate-500 dark:text-gray-400">#{run.id}</span>
                </div>
                <div className="flex items-center gap-3 tabular-nums">
                  <span>+{run.new_papers ?? 0} papers</span>
                  <span>+{run.valid_triples ?? 0} triples</span>
                  <span className="text-slate-400 dark:text-gray-500">{fmtDuration(run.elapsed_s)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
