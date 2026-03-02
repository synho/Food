"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { fetchKgStats, type KgStats } from "@/lib/api";
import {
  DonutChart,
  RingScore,
  EntityBarChart,
  RelBarChart,
  StatCard,
} from "@/components/kg/ChartComponents";
import { TrendChart } from "@/components/kg/TrendChart";
import { PipelinePanel } from "@/components/kg/PipelinePanel";

const AUTO_REFRESH_MS = 60_000;

export default function KgDashboardPage() {
  const [stats, setStats] = useState<KgStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [at, setAt] = useState<Date | null>(null);
  const [autoRefreshing, setAutoRefreshing] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (isAuto = false) => {
    if (isAuto) {
      setAutoRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await fetchKgStats();
      setStats(data);
      setAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load KG stats");
    } finally {
      setLoading(false);
      setAutoRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    timerRef.current = setInterval(() => load(true), AUTO_REFRESH_MS);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [load]);

  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-gray-950 dark:to-gray-900">
        <div className="mx-auto max-w-5xl px-4 py-12 flex items-center gap-3 text-slate-600 dark:text-gray-400">
          <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-400 border-t-transparent dark:border-gray-500" />
          Loading KG status…
        </div>
      </div>
    );
  }

  const neo        = stats?.neo4j;
  const pipeline   = stats?.pipeline;
  const trend      = stats?.trend;
  const neoError   = neo && "error" in neo ? (neo as { error?: string }).error : null;
  const neoErrType = neo && "error_type" in neo ? (neo as { error_type?: string }).error_type : null;
  const neoDebug   = neo && "debug" in neo ? (neo as { debug?: { uri?: string; user?: string } }).debug : null;
  const isConnRefused = neoErrType === "connection_refused";

  const byLabel    = (neo && !neoError && neo.by_label) ? neo.by_label : {};
  const byRelType  = (neo && !neoError && neo.by_relationship_type) ? neo.by_relationship_type : {};
  const labelEntries = Object.entries(byLabel).sort((a, b) => b[1] - a[1]) as [string, number][];
  const totalNodes = labelEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-gray-950 dark:to-gray-900">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10 dark:border-gray-700 dark:bg-gray-900/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 flex-wrap gap-2">
          <div className="flex items-center gap-4 flex-wrap">
            <Link href="/" className="text-slate-500 transition hover:text-slate-800 dark:text-gray-400 dark:hover:text-gray-200">← Home</Link>
            <span className="text-slate-300 dark:text-gray-600">|</span>
            <Link href="/map" className="text-slate-500 transition hover:text-slate-800 dark:text-gray-400 dark:hover:text-gray-200">Health Map</Link>
            <span className="text-slate-300 dark:text-gray-600">|</span>
            <Link href="/clinical" className="text-slate-500 transition hover:text-slate-800 dark:text-gray-400 dark:hover:text-gray-200">Clinical Explorer</Link>
            <span className="text-slate-300 dark:text-gray-600">|</span>
            <Link href="/kg/explore" className="rounded-lg bg-teal-600 px-3 py-1 text-sm font-medium text-white hover:bg-teal-700">Graph Explorer →</Link>
            <h1 className="text-xl font-semibold text-slate-800 dark:text-gray-100">Knowledge Graph — Status</h1>
          </div>
          <div className="flex items-center gap-3">
            {at && (
              <span className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-gray-400">
                {autoRefreshing && (
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border border-slate-400 border-t-transparent dark:border-gray-500" />
                )}
                Updated {at.toLocaleTimeString()}
              </span>
            )}
            <button
              type="button"
              onClick={() => load(false)}
              disabled={loading}
              className="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-600 dark:hover:bg-slate-500"
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        {error && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">{error}</div>
        )}

        {/* ── Overview ─────────────────────────────────────────────────────── */}
        <section className="mb-10">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">Overview</h2>

          {neoError ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
              <p className="font-semibold text-lg">
                {isConnRefused
                  ? "Neo4j connection failed — not running"
                  : "Neo4j connection failed — authentication error"}
              </p>
              <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
                {isConnRefused
                  ? "Neo4j is not started. Start it first using one of the commands below."
                  : "This project uses Neo4j credentials foodnot4self / foodnot4self. The running Neo4j instance may have been created with different credentials."}
              </p>
              {neoDebug?.uri && (
                <p className="mt-2 rounded bg-amber-100/80 px-2 py-1 font-mono text-xs text-amber-900 dark:bg-amber-900/30 dark:text-amber-200">
                  Attempted: {neoDebug.uri} (user: {neoDebug.user ?? "—"})
                </p>
              )}
              <p className="mt-3 text-sm font-semibold text-amber-900 dark:text-amber-200">How to fix:</p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-amber-800 dark:text-amber-300">
                <li><strong>One command:</strong> from repo root run <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">./run.sh start</code> (Neo4j + API + web, credentials pre-set to foodnot4self)</li>
                <li><strong>Docker:</strong> <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">docker compose up -d neo4j</code> or <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">cd kg_pipeline && docker-compose up -d</code></li>
                <li><strong>Reset Docker volume:</strong> if credentials mismatch, run <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">docker compose down -v</code> then <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">docker compose up -d neo4j</code> (data will be reset)</li>
                <li><strong>Homebrew Neo4j:</strong> <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">brew services start neo4j</code>. If credentials differ, create user <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">foodnot4self</code> in the Neo4j browser at http://localhost:7474.</li>
              </ul>
              <details className="mt-3 text-xs text-amber-700 dark:text-amber-400">
                <summary className="cursor-pointer">Error details</summary>
                <pre className="mt-1 overflow-auto rounded bg-amber-100 p-2 dark:bg-amber-900/30">{neoError}</pre>
              </details>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {/* Donut + legend */}
              <div className="col-span-1 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col items-center justify-center dark:border-gray-700 dark:bg-gray-800">
                {labelEntries.length > 0
                  ? <DonutChart data={labelEntries} />
                  : <p className="text-slate-400 text-sm text-center dark:text-gray-500">No nodes yet.<br/>Run the pipeline.</p>
                }
              </div>

              {/* Stat cards */}
              <div className="col-span-1 lg:col-span-2 grid grid-cols-2 gap-4 content-start">
                <StatCard
                  title="Total nodes"
                  value={neo?.nodes != null ? neo.nodes.toLocaleString() : "—"}
                  sub={`across ${Object.keys(byLabel).length} entity types`}
                  accent="blue"
                />
                <StatCard
                  title="Total relationships"
                  value={neo?.relationships != null ? neo.relationships.toLocaleString() : "—"}
                  sub={`across ${Object.keys(byRelType).length} predicate types`}
                  accent="emerald"
                />
                {pipeline && (
                  <>
                    <StatCard
                      title="Pipeline triples"
                      value={pipeline.triples.toLocaleString()}
                      sub="In master_graph.json"
                      accent="violet"
                    />
                    <StatCard
                      title="Unique papers"
                      value={pipeline.unique_sources.toLocaleString()}
                      sub={`${pipeline.with_source_id.toLocaleString()} with source_id`}
                      accent="violet"
                    />
                  </>
                )}
              </div>

              {/* Zero-error ring score */}
              {pipeline && pipeline.triples > 0 && (
                <div className="col-span-1 sm:col-span-2 lg:col-span-1 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col items-center justify-center dark:border-gray-700 dark:bg-gray-800">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">
                    Data quality
                  </p>
                  <RingScore value={pipeline.with_source_id} total={pipeline.triples} />
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Pipeline + Trend row ─────────────────────────────────────────── */}
        {!neoError && (
          <section className="mb-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <PipelinePanel />
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">
                KG Growth Trend
              </h3>
              <p className="mb-3 text-xs text-slate-400 dark:text-gray-500">Node and relationship counts over time</p>
              {trend && trend.length >= 2 ? (
                <>
                  <TrendChart data={trend} />
                  <div className="mt-3 flex items-center justify-center gap-4 text-xs text-slate-500 dark:text-gray-400">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-6 rounded bg-blue-500" /> Nodes
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-6 rounded bg-green-500" /> Relationships
                    </span>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-400 py-8 text-center dark:text-gray-500">
                  Growth trend will appear after multiple pipeline runs.
                </p>
              )}
            </div>
          </section>
        )}

        {/* ── Nodes by type ─────────────────────────────────────────────────── */}
        {!neoError && neo && (
          <>
            <section className="mb-10">
              <div className="mb-4 flex items-end justify-between">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">
                    Nodes by entity type
                  </h2>
                  <p className="mt-0.5 text-xs text-slate-400 dark:text-gray-500">
                    What kinds of entities are in the knowledge graph
                  </p>
                </div>
                {totalNodes > 0 && (
                  <span className="text-xs text-slate-400 tabular-nums dark:text-gray-500">
                    {totalNodes.toLocaleString()} total
                  </span>
                )}
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                {Object.keys(byLabel).length > 0
                  ? <EntityBarChart data={byLabel} />
                  : <p className="text-slate-400 dark:text-gray-500">No node labels yet. Run the pipeline and ingest to Neo4j.</p>
                }
              </div>
            </section>

            {/* ── Relationships by type ──────────────────────────────────────── */}
            <section className="mb-10">
              <div className="mb-4 flex items-end justify-between">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-gray-400">
                    Relationships by predicate type
                  </h2>
                  <p className="mt-0.5 text-xs text-slate-400 dark:text-gray-500">
                    How entities are connected — color coded by semantic group
                  </p>
                </div>
                {neo.relationships != null && (
                  <span className="text-xs text-slate-400 tabular-nums dark:text-gray-500">
                    {neo.relationships.toLocaleString()} total
                  </span>
                )}
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                {Object.keys(byRelType).length > 0
                  ? <RelBarChart data={byRelType} />
                  : <p className="text-slate-400 dark:text-gray-500">No relationship types yet.</p>
                }
              </div>
            </section>
          </>
        )}

        {/* Auto-refresh indicator */}
        <p className="text-center text-xs text-slate-400 mb-4 dark:text-gray-500">
          Auto-refresh every 60s
        </p>
      </main>
    </div>
  );
}
