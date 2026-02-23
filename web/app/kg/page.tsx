"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { fetchKgStats, type KgStats } from "@/lib/api";

// ─── Color palettes ────────────────────────────────────────────────────────────
const ENTITY_HEX: Record<string, string> = {
  Food:              "#22c55e",
  Disease:           "#ef4444",
  Nutrient:          "#3b82f6",
  Symptom:           "#f97316",
  Drug:              "#a855f7",
  BodySystem:        "#06b6d4",
  LifestyleFactor:   "#eab308",
  AgeRelatedChange:  "#6366f1",
  LifeStage:         "#ec4899",
  Study:             "#94a3b8",
};

const ENTITY_TWBG: Record<string, string> = {
  Food:              "bg-green-500",
  Disease:           "bg-red-500",
  Nutrient:          "bg-blue-500",
  Symptom:           "bg-orange-500",
  Drug:              "bg-purple-500",
  BodySystem:        "bg-cyan-500",
  LifestyleFactor:   "bg-yellow-500",
  AgeRelatedChange:  "bg-indigo-500",
  LifeStage:         "bg-pink-500",
  Study:             "bg-slate-400",
};

const ENTITY_DESC: Record<string, string> = {
  Food:              "Foods & dietary items",
  Disease:           "Medical conditions & disorders",
  Nutrient:          "Vitamins, minerals & compounds",
  Symptom:           "Clinical signs & symptoms",
  Drug:              "Medications & treatments",
  BodySystem:        "Organ systems & physiological domains",
  LifestyleFactor:   "Exercise, sleep, stress & habits",
  AgeRelatedChange:  "Normative age-related changes",
  LifeStage:         "Life phases & age bands",
  Study:             "Published studies (schema reserved)",
};

type RelGroup = "beneficial" | "harmful" | "structural" | "relational";

function relGroup(rel: string): RelGroup {
  if (["PREVENTS", "REDUCES_RISK_OF", "ALLEVIATES", "TREATS"].includes(rel)) return "beneficial";
  if (["CAUSES", "AGGRAVATES", "INCREASES_RISK_OF"].includes(rel)) return "harmful";
  if (["CONTAINS", "PART_OF", "OCCURS_AT"].includes(rel)) return "structural";
  return "relational";
}

const GROUP_HEX: Record<RelGroup, string> = {
  beneficial: "#22c55e",
  harmful:    "#ef4444",
  structural: "#3b82f6",
  relational: "#a855f7",
};

const GROUP_LABEL: Record<RelGroup, string> = {
  beneficial: "Beneficial",
  harmful:    "Harmful",
  structural: "Structural",
  relational: "Relational",
};

const REL_DESC: Record<string, string> = {
  PREVENTS:         "Reduces risk of disease onset",
  CAUSES:           "Increases risk or directly causes",
  TREATS:           "Used in treatment or management",
  CONTAINS:         "Food → Nutrient link",
  AGGRAVATES:       "Worsens a condition or symptom",
  REDUCES_RISK_OF:  "Lowers risk of disease",
  ALLEVIATES:       "Reduces symptom severity",
  EARLY_SIGNAL_OF:  "Early indicator of disease",
  SUBSTITUTES_FOR:  "Can partly replace a drug",
  COMPLEMENTS_DRUG: "Works together with a drug",
  AFFECTS:          "General effect (direction unspecified)",
  PART_OF:          "Part of an organ system",
  OCCURS_AT:        "Occurs at this life stage",
  INCREASES_RISK_OF:"Raises disease risk",
  MODIFIABLE_BY:    "Can be slowed/reversed by diet or exercise",
  EXPLAINS_WHY:     "Explains a health mechanism",
  RELATES_TO:       "General relationship (unclassified)",
};

// ─── SVG Donut chart ───────────────────────────────────────────────────────────
function DonutChart({ data }: { data: [string, number][] }) {
  const total = data.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return null;

  const R = 38;
  const CX = 55;
  const CY = 55;
  const C = 2 * Math.PI * R;

  let cumDeg = -90; // start from top
  const segments = data.map(([label, value]) => {
    const frac = value / total;
    const startDeg = cumDeg;
    cumDeg += frac * 360;
    return { label, value, frac, startDeg };
  });

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 110 110" className="w-36 h-36">
        {/* Background circle */}
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="#e2e8f0" strokeWidth={16} />
        {segments.map(({ label, frac, startDeg }) => (
          <circle
            key={label}
            cx={CX}
            cy={CY}
            r={R}
            fill="none"
            stroke={ENTITY_HEX[label] ?? "#94a3b8"}
            strokeWidth={16}
            strokeDasharray={`${frac * C} ${C}`}
            transform={`rotate(${startDeg}, ${CX}, ${CY})`}
          />
        ))}
        {/* Center label */}
        <text
          x={CX} y={CY - 6}
          textAnchor="middle"
          style={{ fontSize: "15px", fontWeight: "700", fill: "#0f172a" }}
        >
          {total.toLocaleString()}
        </text>
        <text
          x={CX} y={CY + 9}
          textAnchor="middle"
          style={{ fontSize: "7px", fill: "#64748b", letterSpacing: "0.08em" }}
        >
          NODES
        </text>
      </svg>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
        {segments.map(({ label, value }) => (
          <div key={label} className="flex items-center gap-1 text-xs text-slate-600">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: ENTITY_HEX[label] ?? "#94a3b8" }}
            />
            <span>{label}</span>
            <span className="text-slate-400 tabular-nums">({value})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Ring score (zero-error compliance) ───────────────────────────────────────
function RingScore({ value, total }: { value: number; total: number }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  const R = 30;
  const C = 2 * Math.PI * R;
  const strokeLen = (pct / 100) * C;
  const color = pct >= 95 ? "#22c55e" : pct >= 80 ? "#f59e0b" : "#ef4444";
  const label = pct >= 95 ? "Excellent" : pct >= 80 ? "Good" : "Needs work";

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 76 76" className="w-20 h-20">
        <circle cx={38} cy={38} r={R} fill="none" stroke="#e2e8f0" strokeWidth={10} />
        <circle
          cx={38} cy={38} r={R}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeDasharray={`${strokeLen} ${C}`}
          strokeLinecap="round"
          transform="rotate(-90, 38, 38)"
        />
        <text
          x={38} y={35}
          textAnchor="middle"
          style={{ fontSize: "13px", fontWeight: "700", fill: color }}
        >
          {pct}%
        </text>
        <text
          x={38} y={47}
          textAnchor="middle"
          style={{ fontSize: "6px", fill: "#64748b" }}
        >
          {label}
        </text>
      </svg>
      <p className="mt-1 text-center text-xs font-medium text-slate-700">Source ID Coverage</p>
      <p className="text-center text-xs text-slate-400">
        {value.toLocaleString()} / {total.toLocaleString()} triples
      </p>
    </div>
  );
}

// ─── Entity bar chart (colored per type, with descriptions) ───────────────────
function EntityBarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="space-y-4">
      {entries.map(([label, value]) => {
        const bg = ENTITY_TWBG[label] ?? "bg-slate-400";
        const hex = ENTITY_HEX[label] ?? "#94a3b8";
        const desc = ENTITY_DESC[label] ?? "Entity in the knowledge graph";
        const pct = Math.round((value / max) * 100);
        return (
          <div key={label}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: hex }}
                />
                <span className="text-sm font-semibold text-slate-800">{label}</span>
              </div>
              <span className="text-sm tabular-nums font-medium text-slate-600">
                {value.toLocaleString()}
              </span>
            </div>
            <div className="h-5 rounded-md bg-slate-100 overflow-hidden">
              <div
                className={`h-full rounded-md ${bg} transition-all duration-700`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-0.5 text-xs text-slate-400">{desc}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── Relationship bar chart (semantic colors, with descriptions) ──────────────
function RelBarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div>
      {/* Group legend */}
      <div className="mb-5 flex flex-wrap gap-3">
        {(["beneficial", "harmful", "structural", "relational"] as RelGroup[]).map((g) => (
          <div key={g} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ backgroundColor: GROUP_HEX[g] }}
            />
            {GROUP_LABEL[g]}
          </div>
        ))}
      </div>

      <div className="space-y-4">
        {entries.map(([label, value]) => {
          const grp = relGroup(label);
          const hex = GROUP_HEX[grp];
          const desc = REL_DESC[label] ?? "Relationship in the knowledge graph";
          const pct = Math.round((value / max) * 100);
          return (
            <div key={label}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 rounded-sm flex-shrink-0"
                    style={{ backgroundColor: hex }}
                  />
                  <span className="text-sm font-semibold text-slate-800">{label}</span>
                </div>
                <span className="text-sm tabular-nums font-medium text-slate-600">
                  {value.toLocaleString()}
                </span>
              </div>
              <div className="h-5 rounded-md bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-md transition-all duration-700"
                  style={{ width: `${pct}%`, backgroundColor: hex }}
                />
              </div>
              <p className="mt-0.5 text-xs text-slate-400">{desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────
function StatCard({
  title, value, sub, accent = "blue",
}: {
  title: string; value: string | number; sub?: string; accent?: "blue" | "emerald" | "violet";
}) {
  const border = accent === "blue" ? "border-blue-200" : accent === "emerald" ? "border-emerald-200" : "border-violet-200";
  const bg     = accent === "blue" ? "bg-blue-50"     : accent === "emerald" ? "bg-emerald-50"     : "bg-violet-50";
  return (
    <div className={`rounded-xl border-2 ${border} ${bg} p-4 shadow-sm`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-gray-900">{value}</div>
      {sub != null && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function KgDashboardPage() {
  const [stats, setStats] = useState<KgStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [at, setAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchKgStats();
      setStats(data);
      setAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load KG stats");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
        <div className="mx-auto max-w-5xl px-4 py-12 flex items-center gap-3 text-slate-600">
          <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
          Loading KG status…
        </div>
      </div>
    );
  }

  const neo        = stats?.neo4j;
  const pipeline   = stats?.pipeline;
  const neoError   = neo && "error" in neo ? (neo as { error?: string }).error : null;
  const neoErrType = neo && "error_type" in neo ? (neo as { error_type?: string }).error_type : null;
  const neoDebug   = neo && "debug" in neo ? (neo as { debug?: { uri?: string; user?: string } }).debug : null;
  const isConnRefused = neoErrType === "connection_refused";

  const byLabel    = (neo && !neoError && neo.by_label) ? neo.by_label : {};
  const byRelType  = (neo && !neoError && neo.by_relationship_type) ? neo.by_relationship_type : {};
  const labelEntries = Object.entries(byLabel).sort((a, b) => b[1] - a[1]) as [string, number][];
  const totalNodes = labelEntries.reduce((s, [, v]) => s + v, 0);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-slate-500 transition hover:text-slate-800">← Home</Link>
            <span className="text-slate-300">|</span>
            <Link href="/map" className="text-slate-500 transition hover:text-slate-800">Health Map</Link>
            <h1 className="text-xl font-semibold text-slate-800">Knowledge Graph — Status</h1>
          </div>
          <div className="flex items-center gap-3">
            {at && <span className="text-sm text-slate-500">Updated {at.toLocaleTimeString()}</span>}
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        {error && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-800">{error}</div>
        )}

        {/* ── Overview ─────────────────────────────────────────────────────── */}
        <section className="mb-10">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Overview</h2>

          {neoError ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
              <p className="font-semibold text-lg">
                {isConnRefused
                  ? "Neo4j connection failed — not running"
                  : "Neo4j connection failed — authentication error"}
              </p>
              <p className="mt-1 text-sm text-amber-800">
                {isConnRefused
                  ? "Neo4j is not started. Start it first using one of the commands below."
                  : "This project uses Neo4j credentials foodnot4self / foodnot4self. The running Neo4j instance may have been created with different credentials."}
              </p>
              {neoDebug?.uri && (
                <p className="mt-2 rounded bg-amber-100/80 px-2 py-1 font-mono text-xs text-amber-900">
                  Attempted: {neoDebug.uri} (user: {neoDebug.user ?? "—"})
                </p>
              )}
              <p className="mt-3 text-sm font-semibold text-amber-900">How to fix:</p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-amber-800">
                <li><strong>One command:</strong> from repo root run <code className="rounded bg-amber-100 px-1">./run.sh start</code> (Neo4j + API + web, credentials pre-set to foodnot4self)</li>
                <li><strong>Docker:</strong> <code className="rounded bg-amber-100 px-1">docker compose up -d neo4j</code> or <code className="rounded bg-amber-100 px-1">cd kg_pipeline && docker-compose up -d</code></li>
                <li><strong>Reset Docker volume:</strong> if credentials mismatch, run <code className="rounded bg-amber-100 px-1">docker compose down -v</code> then <code className="rounded bg-amber-100 px-1">docker compose up -d neo4j</code> (data will be reset)</li>
                <li><strong>Homebrew Neo4j:</strong> <code className="rounded bg-amber-100 px-1">brew services start neo4j</code>. If credentials differ, create user <code className="rounded bg-amber-100 px-1">foodnot4self</code> in the Neo4j browser at http://localhost:7474.</li>
              </ul>
              <details className="mt-3 text-xs text-amber-700">
                <summary className="cursor-pointer">Error details</summary>
                <pre className="mt-1 overflow-auto rounded bg-amber-100 p-2">{neoError}</pre>
              </details>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {/* Donut + legend */}
              <div className="col-span-1 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col items-center justify-center">
                {labelEntries.length > 0
                  ? <DonutChart data={labelEntries} />
                  : <p className="text-slate-400 text-sm text-center">No nodes yet.<br/>Run the pipeline.</p>
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
                <div className="col-span-1 sm:col-span-2 lg:col-span-1 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col items-center justify-center">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Data quality
                  </p>
                  <RingScore value={pipeline.with_source_id} total={pipeline.triples} />
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Nodes by type ─────────────────────────────────────────────────── */}
        {!neoError && neo && (
          <>
            <section className="mb-10">
              <div className="mb-4 flex items-end justify-between">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Nodes by entity type
                  </h2>
                  <p className="mt-0.5 text-xs text-slate-400">
                    What kinds of entities are in the knowledge graph
                  </p>
                </div>
                {totalNodes > 0 && (
                  <span className="text-xs text-slate-400 tabular-nums">
                    {totalNodes.toLocaleString()} total
                  </span>
                )}
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                {Object.keys(byLabel).length > 0
                  ? <EntityBarChart data={byLabel} />
                  : <p className="text-slate-400">No node labels yet. Run the pipeline and ingest to Neo4j.</p>
                }
              </div>
            </section>

            {/* ── Relationships by type ──────────────────────────────────────── */}
            <section className="mb-10">
              <div className="mb-4 flex items-end justify-between">
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Relationships by predicate type
                  </h2>
                  <p className="mt-0.5 text-xs text-slate-400">
                    How entities are connected — color coded by semantic group
                  </p>
                </div>
                {neo.relationships != null && (
                  <span className="text-xs text-slate-400 tabular-nums">
                    {neo.relationships.toLocaleString()} total
                  </span>
                )}
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                {Object.keys(byRelType).length > 0
                  ? <RelBarChart data={byRelType} />
                  : <p className="text-slate-400">No relationship types yet.</p>
                }
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
