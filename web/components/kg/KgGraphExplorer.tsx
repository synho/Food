"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { fetchKgExplore } from "@/lib/api";
import type { KgExploreNode, KgExploreEdge } from "@/lib/types";

// Load ForceGraph2D client-side only (WebGL/Canvas — no SSR)
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

// ── Node type colours ──────────────────────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
  Food:              "#22c55e",
  Disease:           "#ef4444",
  Nutrient:          "#3b82f6",
  Biomarker:         "#f59e0b",
  Mechanism:         "#8b5cf6",
  Drug:              "#ec4899",
  Symptom:           "#f97316",
  LifestyleFactor:   "#14b8a6",
  BodySystem:        "#64748b",
  AgeRelatedChange:  "#ca8a04",
  BiochemicalPathway:"#0ea5e9",
  PopulationGroup:   "#7c3aed",
  Study:             "#6b7280",
};
const DEFAULT_COLOR = "#94a3b8";
const CENTER_COLOR  = "#fbbf24";   // amber — highlight center node

function nodeColor(node: KgExploreNode): string {
  if (node.is_center) return CENTER_COLOR;
  return NODE_COLORS[node.type] ?? DEFAULT_COLOR;
}

// ── Relationship type colors ───────────────────────────────────────────────
const REL_COLORS: Record<string, string> = {
  INCREASES_RISK_OF:  "#ef4444",
  CAUSES:             "#dc2626",
  ALLEVIATES:         "#22c55e",
  REDUCES_RISK_OF:    "#16a34a",
  TREATS:             "#4ade80",
  BIOMARKER_FOR:      "#f59e0b",
  TARGETS_MECHANISM:  "#8b5cf6",
  CONTAINS:           "#3b82f6",
  MODIFIABLE_BY:      "#14b8a6",
  INCREASES_BIOMARKER:"#f97316",
  DECREASES_BIOMARKER:"#22d3ee",
  RELATES_TO:         "#94a3b8",
  EARLY_SIGNAL_OF:    "#f472b6",
  PREVENTS:           "#4ade80",
  COMPLEMENTS_DRUG:   "#a78bfa",
};
const DEFAULT_LINK_COLOR = "#cbd5e1";

function linkColor(link: { type: string }): string {
  return REL_COLORS[link.type] ?? DEFAULT_LINK_COLOR;
}

// ── Legend ─────────────────────────────────────────────────────────────────
const LEGEND_ENTRIES = Object.entries(NODE_COLORS).slice(0, 12);

function Legend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
      <div className="flex items-center gap-1.5 text-xs text-slate-600">
        <span className="inline-block h-3 w-3 rounded-full border-2 border-amber-400 bg-amber-300" />
        Center
      </div>
      {LEGEND_ENTRIES.map(([type, color]) => (
        <div key={type} className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />
          {type}
        </div>
      ))}
    </div>
  );
}

// ── Tooltip ────────────────────────────────────────────────────────────────
interface TooltipState {
  x: number;
  y: number;
  node?: KgExploreNode;
  edge?: KgExploreEdge;
}

// ── Main component ─────────────────────────────────────────────────────────
export function KgGraphExplorer() {
  const [query,   setQuery]   = useState("");
  const [input,   setInput]   = useState("");
  const [hops,    setHops]    = useState<1 | 2>(1);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [center,  setCenter]  = useState<string | null>(null);
  const [nodes,   setNodes]   = useState<KgExploreNode[]>([]);
  const [edges,   setEdges]   = useState<KgExploreEdge[]>([]);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [activeRels,  setActiveRels]  = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 800, h: 520 });

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
      const e = entries[0];
      if (e) setDims({ w: e.contentRect.width, h: Math.max(400, e.contentRect.height) });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Fetch graph
  useEffect(() => {
    if (!query) return;
    setLoading(true);
    setError(null);
    fetchKgExplore(query, hops, 120)
      .then(data => {
        if (!data.center) {
          setError(`No entity found matching "${query}"`);
          setNodes([]); setEdges([]); setCenter(null);
          return;
        }
        setCenter(data.center);
        setNodes(data.nodes);
        setEdges(data.edges);
        setActiveTypes(new Set(data.nodes.map(n => n.type)));
        setActiveRels(new Set(data.edges.map(e => e.type)));
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [query, hops]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) setQuery(input.trim());
  };

  // Filter graph data
  const visibleNodes = nodes.filter(n => n.is_center || activeTypes.has(n.type));
  const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = edges.filter(
    e => activeRels.has(e.type) && visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
  );

  const graphData = {
    nodes: visibleNodes.map(n => ({ ...n })),
    links: visibleEdges.map(e => ({ source: e.source, target: e.target, type: e.type, context: e.context })),
  };

  const toggleType = (t: string) =>
    setActiveTypes(prev => { const s = new Set(prev); s.has(t) ? s.delete(t) : s.add(t); return s; });

  const toggleRel = (r: string) =>
    setActiveRels(prev => { const s = new Set(prev); s.has(r) ? s.delete(r) : s.add(r); return s; });

  // All types and rels present in this graph
  const allTypes = Array.from(new Set(nodes.map(n => n.type))).sort();
  const allRels  = Array.from(new Set(edges.map(e => e.type))).sort();

  const handleNodeClick = useCallback((node: Record<string, unknown>) => {
    setInput(String(node.name ?? ""));
    setQuery(String(node.name ?? ""));
  }, []);

  const handleNodeHover = useCallback((node: Record<string, unknown> | null) => {
    if (!node) { setTooltip(null); return; }
    // position near mouse — approximate from center
    setTooltip({ x: dims.w / 2, y: 60, node: node as unknown as KgExploreNode });
  }, [dims]);

  const handleLinkHover = useCallback((link: Record<string, unknown> | null) => {
    if (!link) { setTooltip(null); return; }
    setTooltip({ x: dims.w / 2, y: 60, edge: link as unknown as KgExploreEdge });
  }, [dims]);

  return (
    <div className="flex flex-col gap-4">
      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Enter any entity — disease, food, nutrient, biomarker…"
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 shadow-sm outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-400"
        />
        <select
          value={hops}
          onChange={e => setHops(Number(e.target.value) as 1 | 2)}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 shadow-sm"
        >
          <option value={1}>1 hop</option>
          <option value={2}>2 hops</option>
        </select>
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Explore"}
        </button>
      </form>

      {/* Quick examples */}
      {!center && !loading && (
        <div className="flex flex-wrap gap-2">
          {["Type 2 diabetes", "Omega-3", "Vitamin D", "Hypertension", "Gut microbiome", "Alzheimer's disease", "Metformin", "Inflammation"].map(ex => (
            <button
              key={ex}
              onClick={() => { setInput(ex); setQuery(ex); }}
              className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs text-teal-700 hover:bg-teal-100"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{error}</div>
      )}

      {center && !loading && (
        <>
          {/* Stats row */}
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600">
            <span>Center: <strong className="text-slate-900">{center}</strong></span>
            <span>{visibleNodes.length} nodes · {visibleEdges.length} edges shown</span>
            <span className="text-slate-400">Click a node to re-center</span>
          </div>

          {/* Filters */}
          <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm space-y-2">
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Node types</p>
              <div className="flex flex-wrap gap-1.5">
                {allTypes.map(t => (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium border transition ${
                      activeTypes.has(t)
                        ? "border-transparent text-white"
                        : "border-slate-200 bg-white text-slate-400"
                    }`}
                    style={activeTypes.has(t) ? { background: NODE_COLORS[t] ?? DEFAULT_COLOR } : {}}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">Relationship types</p>
              <div className="flex flex-wrap gap-1.5">
                {allRels.map(r => (
                  <button
                    key={r}
                    onClick={() => toggleRel(r)}
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium border transition ${
                      activeRels.has(r)
                        ? "border-transparent text-white"
                        : "border-slate-200 bg-white text-slate-400"
                    }`}
                    style={activeRels.has(r) ? { background: REL_COLORS[r] ?? DEFAULT_LINK_COLOR, color: "#fff" } : {}}
                  >
                    {r.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Graph canvas */}
      {center && (
        <div
          ref={containerRef}
          className="relative rounded-2xl border border-slate-200 bg-slate-950 overflow-hidden shadow-lg"
          style={{ height: 520 }}
        >
          {tooltip && (
            <div className="absolute top-3 left-3 z-10 max-w-xs rounded-xl border border-slate-700 bg-slate-900/95 p-3 text-xs text-white shadow-xl">
              {tooltip.node && (
                <>
                  <p className="font-semibold text-sm">{tooltip.node.name}</p>
                  <p style={{ color: NODE_COLORS[tooltip.node.type] ?? DEFAULT_COLOR }}>
                    {tooltip.node.type}{tooltip.node.is_center ? " · center" : ""}
                  </p>
                </>
              )}
              {tooltip.edge && (
                <>
                  <p className="font-semibold" style={{ color: REL_COLORS[tooltip.edge.type] ?? DEFAULT_LINK_COLOR }}>
                    {tooltip.edge.type.replace(/_/g, " ")}
                  </p>
                  {tooltip.edge.context && (
                    <p className="mt-1 text-slate-300 line-clamp-3">{tooltip.edge.context}</p>
                  )}
                  {tooltip.edge.source_id && (
                    <p className="mt-1 text-slate-500">{tooltip.edge.source_id}</p>
                  )}
                </>
              )}
            </div>
          )}
          <ForceGraph2D
            graphData={graphData}
            width={dims.w}
            height={520}
            backgroundColor="#020617"
            nodeColor={(n) => nodeColor(n as unknown as KgExploreNode)}
            nodeLabel={(n) => `${(n as KgExploreNode).name} (${(n as KgExploreNode).type})`}
            nodeRelSize={5}
            nodeVal={(n) => (n as KgExploreNode).is_center ? 3 : 1}
            linkColor={(l) => linkColor(l as { type: string })}
            linkWidth={1}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={(l) => (l as { type: string }).type.replace(/_/g, " ")}
            onNodeClick={handleNodeClick as (node: object) => void}
            onNodeHover={handleNodeHover as (node: object | null) => void}
            onLinkHover={handleLinkHover as (link: object | null) => void}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const n = node as KgExploreNode & { x?: number; y?: number };
              if (n.x == null || n.y == null) return;
              const r = n.is_center ? 8 : 5;
              ctx.beginPath();
              ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
              ctx.fillStyle = nodeColor(n);
              ctx.fill();
              if (n.is_center) {
                ctx.strokeStyle = "#fde68a";
                ctx.lineWidth = 2;
                ctx.stroke();
              }
              // Label at reasonable zoom
              if (globalScale >= 0.8 || n.is_center) {
                const label = n.name.length > 20 ? n.name.slice(0, 18) + "…" : n.name;
                ctx.font = `${n.is_center ? "bold " : ""}${Math.max(8, 11 / globalScale)}px sans-serif`;
                ctx.fillStyle = "#f1f5f9";
                ctx.textAlign = "center";
                ctx.fillText(label, n.x, n.y + r + 10 / globalScale);
              }
            }}
          />
        </div>
      )}

      {/* Legend */}
      {center && (
        <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <Legend />
        </div>
      )}
    </div>
  );
}
