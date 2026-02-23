"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  fetchPosition, fetchSafestPath, fetchEarlySignals, fetchFoodChain, fetchContextFromText,
} from "@/lib/api";
import type { FoodChainResponse } from "@/lib/api";
import type {
  UserContext, PositionResponse, SafestPathResponse,
  EarlySignalGuidanceResponse, NearbyRisk, PathStep,
} from "@/lib/types";

// ─── Map canvas ───────────────────────────────────────────────────────────────
const W = 900;
const H = 480;

// ─── Zone topology ────────────────────────────────────────────────────────────
const ZONE_THRIVING   = "M 0,0 H 900 V 148 Q 650,128 450,138 Q 250,148 0,133 Z";
const ZONE_NAVIGATION = "M 0,128 Q 250,143 450,133 Q 650,123 900,143 V 308 Q 650,283 450,293 Q 250,303 0,283 Z";
const ZONE_RISK       = "M 0,278 Q 250,298 450,288 Q 650,278 900,298 V 422 Q 650,398 450,408 Q 250,418 0,398 Z";
const ZONE_CRITICAL   = "M 0,393 Q 250,413 450,403 Q 650,393 900,413 V 480 H 0 Z";

function getZoneAt(y: number): { name: string; hex: string; light: string; desc: string } {
  if (y < 140) return { name: "Thriving Zone",    hex: "#16a34a", light: "#f0fdf4", desc: "excellent health foundation" };
  if (y < 300) return { name: "Navigation Zone",  hex: "#b45309", light: "#fffbeb", desc: "manageable health landscape" };
  if (y < 415) return { name: "Risk Territory",   hex: "#dc2626", light: "#fff1f2", desc: "active intervention recommended" };
  return              { name: "Critical Zone",    hex: "#7f1d1d", light: "#fef2f2", desc: "immediate action needed" };
}

const TERRITORIES = [
  { x: 125, y: 55,  name: "Nutritional Highlands",  size: 9.5 },
  { x: 720, y: 60,  name: "Longevity Coast",         size: 9.5 },
  { x: 280, y: 198, name: "Metabolic Crossroads",    size: 9   },
  { x: 610, y: 192, name: "Recovery Valley",         size: 9   },
  { x: 155, y: 345, name: "Inflammatory Plains",     size: 8.5 },
  { x: 530, y: 333, name: "Cardiometabolic Ridge",   size: 8.5 },
  { x: 775, y: 348, name: "Neurological Frontier",   size: 8   },
  { x: 420, y: 445, name: "Critical Terrain",        size: 8   },
];

const LIFE_MARKS = [
  { label: "Teens",  x: 110, age: 17 },
  { label: "20s",    x: 210, age: 25 },
  { label: "30s",    x: 330, age: 35 },
  { label: "40s",    x: 452, age: 45 },
  { label: "50s",    x: 572, age: 55 },
  { label: "60s",    x: 692, age: 65 },
  { label: "70s+",   x: 800, age: 75 },
];

// ─── Position math ────────────────────────────────────────────────────────────
function ageToX(age: number | null | undefined): number {
  const a = Math.max(16, Math.min(90, age ?? 35));
  return 80 + ((a - 16) / (90 - 16)) * 760;
}

function conditionsToY(
  conditions: string[], symptoms: string[], age: number | null | undefined
): number {
  const a = age ?? 35;
  const ageBase  = Math.max(0, (a - 20) * 1.7);
  const condRisk = conditions.length * 65;
  const sympRisk = symptoms.length * 18;
  return Math.min(Math.max(50 + ageBase + condRisk + sympRisk, 50), 455);
}

function destinationXY(userX: number, userY: number) {
  return { dx: Math.min(userX + 140, W - 55), dy: Math.max(userY - 138, 68) };
}

function nearTerritory(conditions: string[]): string {
  const t = conditions.join(" ").toLowerCase();
  if (/diabetes|blood sugar|insulin|glucose|metabolic/.test(t)) return "Metabolic Crossroads";
  if (/hypertension|heart|cardiovascular|cholesterol|pressure/.test(t)) return "Cardiometabolic Ridge";
  if (/inflamm|arthritis|autoimmune|lupus/.test(t)) return "Inflammatory Plains";
  if (/sarcopenia|osteoporosis|muscle|bone|joint/.test(t)) return "Musculoskeletal Valley";
  if (/neuro|cognitive|alzheimer|parkinson|dementia/.test(t)) return "Neurological Frontier";
  return "";
}

const RISK_OFFSETS = [
  { dx:  85, dy:  22 }, { dx: 130, dy:  -8 }, { dx:  70, dy:  58 },
  { dx: 158, dy:  30 }, { dx: 105, dy:  78 }, { dx:  48, dy:  44 },
  { dx: 182, dy:  -6 }, { dx: 118, dy:  95 },
];

function riskXY(i: number, ux: number, uy: number) {
  const o = RISK_OFFSETS[i % RISK_OFFSETS.length];
  return { x: Math.min(Math.max(ux + o.dx, 40), W - 40), y: Math.min(Math.max(uy + o.dy, 40), H - 40) };
}

type Sev = "high" | "med" | "low";

function riskSev(r: NearbyRisk): Sev {
  if ((r.kind || "").toLowerCase() === "disease" && (r.evidence?.length ?? 0) >= 2) return "high";
  if ((r.kind || "").toLowerCase() === "disease" || (r.evidence?.length ?? 0) >= 1)  return "med";
  return "low";
}

const SEV_HEX: Record<Sev, string> = { high: "#ef4444", med: "#f97316", low: "#94a3b8" };
const SEV_GLOW: Record<Sev, string> = { high: "#fca5a5", med: "#fdba74", low: "#e2e8f0" };

// ─── Journey narrative ────────────────────────────────────────────────────────
function buildNarrative(
  age: number | null | undefined, gender: string | null | undefined,
  conditions: string[], symptoms: string[], userY: number,
  risks: NearbyRisk[], steps: PathStep[],
): string {
  const a = age ?? 35;
  const decade = `${Math.floor(a / 10) * 10}s`;
  const zone = getZoneAt(userY);
  const territory = nearTerritory(conditions);

  let t = `You are in your **${decade}**`;
  if (gender) t += ` (${gender})`;
  t += `, positioned in the **${zone.name}** — ${zone.desc}.`;

  if (territory) t += ` Your conditions place you near the **${territory}**.`;

  if (conditions.length > 0) {
    t += ` With ${conditions.join(", ")}, the map shows ${risks.length} nearby risk zone${risks.length !== 1 ? "s" : ""} ahead.`;
  } else if (symptoms.length > 0) {
    t += ` Your reported symptoms (${symptoms.join(", ")}) indicate early navigation is advisable.`;
  } else {
    t += " Your health landscape looks open — maintain this trajectory.";
  }

  if (steps.length > 0) t += ` Your safest route begins: **${steps[0].action}**.`;
  return t;
}

function stepHex(action: string): string {
  const a = action.toLowerCase();
  if (/avoid|limit|stop|reduce/.test(a)) return "#f97316";
  if (/consult|doctor|physician|seek/.test(a)) return "#3b82f6";
  return "#16a34a";
}

// ─── Context merge helper ─────────────────────────────────────────────────────
function mergeContexts(base: UserContext, patch: UserContext): UserContext {
  const uniq = (a: string[] | undefined, b: string[] | undefined) => {
    const combined = [...(a ?? []), ...(b ?? [])];
    return combined.filter((v, i) => combined.indexOf(v) === i);
  };
  return {
    ...base,
    age:          patch.age          ?? base.age,
    gender:       patch.gender       ?? base.gender,
    ethnicity:    patch.ethnicity    ?? base.ethnicity,
    location:     patch.location     ?? base.location,
    way_of_living: patch.way_of_living ?? base.way_of_living,
    conditions:   uniq(base.conditions,  patch.conditions),
    symptoms:     uniq(base.symptoms,    patch.symptoms),
    medications:  uniq(base.medications, patch.medications),
    goals:        uniq(base.goals,       patch.goals),
  };
}

// ─── Build a friendly "what's missing" prompt ─────────────────────────────────
function buildRefinePrompt(ctx: UserContext | null): string {
  if (!ctx) return "Tell me about yourself — age, any health conditions, symptoms, goals, or how you've been feeling lately.";
  const missing: string[] = [];
  if (!ctx.medications?.length) missing.push("any medications you take");
  if (!ctx.goals?.length) missing.push("your health goals");
  if (!ctx.way_of_living && !ctx.location) missing.push("your lifestyle or where you live");
  if (missing.length === 0) return "Anything else you'd like to add or update about your health?";
  return `Feel free to share ${missing.join(", ")} — just type naturally, like you're telling a friend.`;
}

// ─── SVG components ───────────────────────────────────────────────────────────
function CompassRose({ cx, cy }: { cx: number; cy: number }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={24} fill="white" fillOpacity="0.88" stroke="#cbd5e1" strokeWidth="1" />
      {[["N", 0, -14], ["S", 0, 18], ["E", 14, 4], ["W", -14, 4]].map(([l, dx, dy]) => (
        <text key={l as string} x={cx + (dx as number)} y={cy + (dy as number)} textAnchor="middle"
          style={{ fontSize: "8px", fill: l === "N" ? "#dc2626" : "#64748b", fontWeight: l === "N" ? "700" : "400" }}>{l}</text>
      ))}
      <polygon points={`${cx},${cy - 12} ${cx + 3},${cy} ${cx - 3},${cy}`} fill="#dc2626" />
      <polygon points={`${cx},${cy + 12} ${cx + 3},${cy} ${cx - 3},${cy}`} fill="#94a3b8" />
    </g>
  );
}

function MapBackground() {
  return (
    <>
      <defs>
        <linearGradient id="g-thriving" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#bbf7d0" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#86efac" stopOpacity="0.60" />
        </linearGradient>
        <linearGradient id="g-navigation" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#fef9c3" stopOpacity="0.75" />
          <stop offset="100%" stopColor="#fde68a" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="g-risk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#fed7aa" stopOpacity="0.70" />
          <stop offset="100%" stopColor="#fca5a5" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="g-critical" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#fca5a5" stopOpacity="0.60" />
          <stop offset="100%" stopColor="#f87171" stopOpacity="0.75" />
        </linearGradient>
        <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
          <path d="M 60 0 L 0 0 0 60" fill="none" stroke="#94a3b8" strokeWidth="0.3" strokeOpacity="0.35" />
        </pattern>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <rect width={W} height={H} fill="#fafaf8" />
      <rect width={W} height={H} fill="url(#grid)" />
      <path d={ZONE_THRIVING}   fill="url(#g-thriving)"   />
      <path d={ZONE_NAVIGATION} fill="url(#g-navigation)" />
      <path d={ZONE_RISK}       fill="url(#g-risk)"       />
      <path d={ZONE_CRITICAL}   fill="url(#g-critical)"   />
      {[
        "M 0,133 Q 250,148 450,138 Q 650,128 900,148",
        "M 0,283 Q 250,303 450,293 Q 650,283 900,303",
        "M 0,398 Q 250,418 450,408 Q 650,398 900,418",
      ].map((d, i) => (
        <path key={i} d={d} fill="none" stroke="#94a3b8" strokeWidth="0.8" strokeOpacity="0.45" />
      ))}
      {TERRITORIES.map((t) => (
        <text key={t.name} x={t.x} y={t.y} textAnchor="middle"
          style={{ fontSize: `${t.size}px`, fontStyle: "italic", fill: "#64748b", opacity: 0.55,
            fontFamily: "serif", letterSpacing: "0.04em", userSelect: "none" }}>
          {t.name}
        </text>
      ))}
      {[
        { label: "THRIVING",   y: 112, color: "#15803d" },
        { label: "NAVIGATION", y: 272, color: "#92400e" },
        { label: "RISK",       y: 388, color: "#b91c1c" },
        { label: "CRITICAL",   y: 458, color: "#7f1d1d" },
      ].map(({ label, y, color }) => (
        <text key={label} x={W - 12} y={y} textAnchor="end"
          style={{ fontSize: "7.5px", fill: color, fontWeight: "700", letterSpacing: "0.1em", opacity: 0.7 }}>
          {label}
        </text>
      ))}
      {LIFE_MARKS.map(({ x }) => (
        <line key={x} x1={x} y1={0} x2={x} y2={H}
          stroke="#94a3b8" strokeWidth="0.6" strokeOpacity="0.35" strokeDasharray="4,5" />
      ))}
    </>
  );
}

function LifeRuler({ userX }: { userX: number }) {
  const RULER_Y = H - 46;
  return (
    <g>
      <rect x={0} y={RULER_Y} width={W} height={46} fill="#f1f5f9" fillOpacity="0.92" />
      <line x1={0} y1={RULER_Y} x2={W} y2={RULER_Y} stroke="#cbd5e1" strokeWidth="1" />
      {LIFE_MARKS.map(({ label, x, age }) => (
        <g key={age}>
          <line x1={x} y1={RULER_Y} x2={x} y2={RULER_Y + 10} stroke="#94a3b8" strokeWidth="1.2" />
          <text x={x} y={RULER_Y + 24} textAnchor="middle"
            style={{ fontSize: "10px", fill: "#475569", fontWeight: "600" }}>{label}</text>
        </g>
      ))}
      <line x1={userX} y1={RULER_Y - 4} x2={userX} y2={RULER_Y + 34}
        stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" />
      <line x1={20} y1={RULER_Y + 36} x2={140} y2={RULER_Y + 36}
        stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />
      <line x1={20} y1={RULER_Y + 31} x2={20} y2={RULER_Y + 41} stroke="#94a3b8" strokeWidth="1.5" />
      <line x1={140} y1={RULER_Y + 31} x2={140} y2={RULER_Y + 41} stroke="#94a3b8" strokeWidth="1.5" />
      <text x={80} y={RULER_Y + 43} textAnchor="middle"
        style={{ fontSize: "7px", fill: "#94a3b8" }}>≈ 20 years</text>
    </g>
  );
}

function SafeRoute({ ux, uy, dx, dy }: { ux: number; uy: number; dx: number; dy: number }) {
  const mx = (ux + dx) / 2;
  const my = Math.min(uy, dy) - 30;
  const d = `M ${ux},${uy} Q ${mx},${my} ${dx},${dy}`;
  return (
    <g>
      <path d={d} fill="none" stroke="#86efac" strokeWidth="6" strokeOpacity="0.35" strokeLinecap="round" />
      <path d={d} fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round"
        strokeDasharray="8,5">
        <animate attributeName="stroke-dashoffset" from="130" to="0" dur="2s" repeatCount="indefinite" />
      </path>
      <circle cx={dx} cy={dy} r={5} fill="#16a34a" opacity="0.9" />
      <circle cx={dx} cy={dy} r={3} fill="white" />
    </g>
  );
}

function DestinationStar({ x, y }: { x: number; y: number }) {
  const pts = Array.from({ length: 10 }, (_, i) => {
    const r = i % 2 === 0 ? 10 : 4.5;
    const angle = (i * 36 - 90) * (Math.PI / 180);
    return `${x + r * Math.cos(angle)},${y + r * Math.sin(angle)}`;
  }).join(" ");
  return (
    <g>
      <circle cx={x} cy={y} r={18} fill="#fef9c3" stroke="#fbbf24" strokeWidth="1.5" opacity="0.8" />
      <polygon points={pts} fill="#f59e0b" stroke="white" strokeWidth="1" />
      <text x={x} y={y + 28} textAnchor="middle"
        style={{ fontSize: "8px", fill: "#92400e", fontWeight: "700" }}>DESTINATION</text>
    </g>
  );
}

function UserMarker({ x, y, label }: { x: number; y: number; label: string }) {
  return (
    <g filter="url(#glow)">
      <circle cx={x} cy={y} r={16} fill="#3b82f6" fillOpacity="0">
        <animate attributeName="r" from="14" to="26" dur="2s" repeatCount="indefinite" />
        <animate attributeName="fill-opacity" from="0.35" to="0" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx={x} cy={y} r={10} fill="#3b82f6" fillOpacity="0">
        <animate attributeName="r" from="9" to="18" dur="2s" begin="0.5s" repeatCount="indefinite" />
        <animate attributeName="fill-opacity" from="0.25" to="0" dur="2s" begin="0.5s" repeatCount="indefinite" />
      </circle>
      <circle cx={x} cy={y} r={9} fill="#2563eb" stroke="white" strokeWidth="2.5" />
      <circle cx={x} cy={y} r={3.5} fill="white" />
      <rect x={x - 38} y={y - 32} width={76} height={18} rx={9}
        fill="#1d4ed8" stroke="white" strokeWidth="1.5" />
      <text x={x} y={y - 20} textAnchor="middle"
        style={{ fontSize: "8.5px", fill: "white", fontWeight: "700" }}>{label}</text>
    </g>
  );
}

function RiskPin({
  x, y, sev, label, selected, onClick,
}: {
  x: number; y: number; sev: Sev; label: string; selected: boolean; onClick: () => void;
}) {
  const fill = SEV_HEX[sev];
  const glow = SEV_GLOW[sev];
  return (
    <g onClick={onClick} style={{ cursor: "pointer" }}
      transform={selected ? `translate(${x},${y}) scale(1.25)` : `translate(${x},${y})`}>
      {selected && <circle r={16} fill={glow} opacity="0.7" />}
      <path d="M 0,-14 C -7,-14 -11,-9 -11,-4 C -11,4 0,16 0,16 C 0,16 11,4 11,-4 C 11,-9 7,-14 0,-14 Z"
        fill={fill} stroke="white" strokeWidth="1.8" />
      <circle cy={-4} r={4} fill="white" opacity="0.85" />
      <text y={28} textAnchor="middle"
        style={{ fontSize: "7.5px", fill, fontWeight: "700", userSelect: "none" }}>
        {label.length > 14 ? label.slice(0, 13) + "…" : label}
      </text>
    </g>
  );
}

function WarningFlag({ x, y, label }: { x: number; y: number; label: string }) {
  return (
    <g transform={`translate(${x},${y})`} style={{ userSelect: "none" }}>
      <line x1={0} y1={0} x2={0} y2={-20} stroke="#f59e0b" strokeWidth="1.8" />
      <polygon points="0,-20 12,-14 0,-8" fill="#f59e0b" opacity="0.9" />
      <text y={10} textAnchor="middle"
        style={{ fontSize: "7px", fill: "#92400e", fontStyle: "italic" }}>
        {label.length > 12 ? label.slice(0, 11) + "…" : label}
      </text>
    </g>
  );
}

function MapLegend() {
  const items = [
    { color: "#2563eb", label: "You are here" },
    { color: "#ef4444", label: "High-risk zone" },
    { color: "#f97316", label: "Medium-risk zone" },
    { color: "#16a34a", label: "Safest route" },
    { color: "#f59e0b", label: "Early signal" },
    { color: "#f59e0b", label: "Destination", star: true },
  ];
  const LX = 14, LY = H - 148;
  return (
    <g>
      <rect x={LX - 6} y={LY - 14} width={132} height={items.length * 17 + 18}
        rx={6} fill="white" fillOpacity="0.88" stroke="#cbd5e1" strokeWidth="1" />
      <text x={LX + 55} y={LY} textAnchor="middle"
        style={{ fontSize: "8px", fill: "#475569", fontWeight: "700", letterSpacing: "0.06em" }}>
        LEGEND
      </text>
      {items.map(({ color, label }, i) => (
        <g key={label} transform={`translate(${LX}, ${LY + 10 + i * 17})`}>
          <circle cy={-3} r={5} fill={color} />
          <text x={12} style={{ fontSize: "8px", fill: "#475569" }}>{label}</text>
        </g>
      ))}
    </g>
  );
}

function NarrativeText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return (
    <span>
      {parts.map((p, i) =>
        i % 2 === 1 ? <strong key={i} className="text-slate-900">{p}</strong> : <span key={i}>{p}</span>
      )}
    </span>
  );
}

function InfoPanel({ risk, onClose }: { risk: NearbyRisk; onClose: () => void }) {
  const sev = riskSev(risk);
  return (
    <div className="relative rounded-xl border-2 bg-white p-4 shadow-lg"
      style={{ borderColor: SEV_HEX[sev] }}>
      <button onClick={onClose}
        className="absolute right-3 top-3 text-slate-400 hover:text-slate-700 text-lg leading-none">×</button>
      <div className="flex items-center gap-2 mb-2">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: SEV_HEX[sev] }} />
        <h3 className="font-bold text-slate-900">{risk.name}</h3>
        <span className="rounded px-1.5 py-0.5 text-xs font-bold text-white"
          style={{ backgroundColor: SEV_HEX[sev] }}>{sev.toUpperCase()}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 capitalize">{risk.kind}</span>
      </div>
      {risk.reason && <p className="text-sm text-slate-700 mb-3 leading-relaxed">{risk.reason}</p>}
      {risk.evidence?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
            Evidence ({risk.evidence.length} source{risk.evidence.length !== 1 ? "s" : ""})
          </p>
          <div className="space-y-1.5">
            {risk.evidence.slice(0, 3).map((ev, i) => (
              <div key={i} className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs">
                <span className={`inline-block rounded px-1 py-0.5 text-xs font-medium mr-1 ${
                  ev.source_type === "FDA" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"
                }`}>{ev.source_type || "PMC"}</span>
                <span className="font-mono text-slate-600">{ev.source_id}</span>
                {ev.journal && <span className="ml-1 italic text-slate-500">{ev.journal}</span>}
                {ev.context && <p className="mt-1 text-slate-500">"{ev.context}"</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ChainPanel({ chain }: { chain: FoodChainResponse }) {
  const beneficial = chain.chain.filter(l =>
    ["PREVENTS","ALLEVIATES","REDUCES_RISK_OF","TREATS"].includes(l.relationship_type));
  return (
    <div className="rounded-xl border border-violet-200 bg-violet-50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="font-bold text-violet-900 text-base">{chain.food}</span>
        <span className="text-xs text-slate-500">{chain.chain.length} chain links</span>
      </div>
      {chain.chain.length === 0 ? (
        <p className="text-sm text-slate-500">No chains found in the KG for this food.</p>
      ) : (
        <div className="space-y-2">
          {beneficial.slice(0, 4).map((l, i) => (
            <div key={i} className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="rounded-full bg-violet-200 text-violet-800 px-2 py-0.5 font-medium">{chain.food}</span>
              <span className="text-slate-400">→</span>
              <span className="rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 font-medium">{l.nutrient}</span>
              <span className="text-slate-400">→</span>
              <span className={`rounded px-1.5 py-0.5 font-bold ${
                ["PREVENTS","ALLEVIATES","REDUCES_RISK_OF"].includes(l.relationship_type)
                  ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
              }`}>{l.relationship_type}</span>
              <span className="text-slate-400">→</span>
              <span className="rounded-full bg-green-100 text-green-800 px-2 py-0.5 font-medium">{l.target}</span>
              <span className="ml-auto text-slate-400">{l.evidence.length} ev.</span>
            </div>
          ))}
          {chain.chain.length > 4 && (
            <p className="text-xs text-slate-400">+{chain.chain.length - 4} more chains</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Profile chip summary ─────────────────────────────────────────────────────
function ProfileChips({ ctx }: { ctx: UserContext }) {
  const chips: Array<{ label: string; color: string }> = [];
  if (ctx.age) chips.push({ label: `Age ${ctx.age}`, color: "bg-blue-100 text-blue-800" });
  if (ctx.gender) chips.push({ label: ctx.gender, color: "bg-slate-100 text-slate-700" });
  (ctx.conditions ?? []).forEach(c => chips.push({ label: c, color: "bg-amber-100 text-amber-800" }));
  (ctx.symptoms ?? []).forEach(s => chips.push({ label: s, color: "bg-orange-100 text-orange-800" }));
  (ctx.medications ?? []).forEach(m => chips.push({ label: m, color: "bg-purple-100 text-purple-800" }));
  (ctx.goals ?? []).forEach(g => chips.push({ label: g, color: "bg-emerald-100 text-emerald-800" }));
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map(({ label, color }, i) => (
        <span key={i} className={`rounded-full px-2.5 py-1 text-xs font-medium ${color}`}>{label}</span>
      ))}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
interface MapState {
  profile: UserContext;
  position: PositionResponse;
  safestPath: SafestPathResponse;
  earlySignals: EarlySignalGuidanceResponse;
  userX: number; userY: number;
}

export default function HealthMapPage() {
  // ── Core state ───────────────────────────────────────────────────────────
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [mapData, setMapData]             = useState<MapState | null>(null);
  const [selectedRisk, setSelectedRisk]   = useState<NearbyRisk | null>(null);

  // ── Context from localStorage (home page) ────────────────────────────────
  const [loadedCtx, setLoadedCtx]         = useState<UserContext | null>(null);

  // ── Conversational refinement panel ─────────────────────────────────────
  const [showRefine, setShowRefine]       = useState(false);
  const [refineText, setRefineText]       = useState("");
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineError, setRefineError]     = useState<string | null>(null);

  // ── New user (no stored context): chat-style intro ───────────────────────
  const [introText, setIntroText]         = useState("");
  const [introLoading, setIntroLoading]   = useState(false);
  const [introError, setIntroError]       = useState<string | null>(null);

  // ── Food chain explorer ──────────────────────────────────────────────────
  const [foodInput, setFoodInput]         = useState("");
  const [chainLoading, setChainLoading]   = useState(false);
  const [chainData, setChainData]         = useState<FoodChainResponse | null>(null);

  const autoSubmitted = useRef(false);

  // ── Core submit function (takes full UserContext) ─────────────────────────
  const submitContext = useCallback(async (ctx: UserContext) => {
    if (!ctx.age && !ctx.conditions?.length && !ctx.symptoms?.length) {
      setError("Share your age, conditions, or symptoms so we can locate you on the map.");
      return;
    }
    setLoading(true);
    setError(null);
    setSelectedRisk(null);
    try {
      const [pos, path, early] = await Promise.all([
        fetchPosition(ctx), fetchSafestPath(ctx), fetchEarlySignals(ctx),
      ]);
      setMapData({
        profile: ctx,
        position: pos,
        safestPath: path,
        earlySignals: early,
        userX: ageToX(ctx.age),
        userY: conditionsToY(ctx.conditions ?? [], ctx.symptoms ?? [], ctx.age),
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(/failed to fetch|network error|load failed/i.test(msg)
        ? "Cannot reach the API server. Is it running?"
        : msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── On mount: read context from localStorage and auto-locate ─────────────
  useEffect(() => {
    if (autoSubmitted.current) return;
    try {
      const raw = localStorage.getItem("health_context");
      if (!raw) return;
      const ctx = JSON.parse(raw) as UserContext;
      if (!ctx || typeof ctx !== "object") return;
      autoSubmitted.current = true;
      setLoadedCtx(ctx);
      submitContext(ctx);
    } catch { /* ignore */ }
  }, [submitContext]);

  // ── New user: parse free-text intro ──────────────────────────────────────
  const handleIntroSubmit = async () => {
    if (!introText.trim()) return;
    setIntroLoading(true);
    setIntroError(null);
    try {
      const ctx = await fetchContextFromText(introText);
      setLoadedCtx(ctx);
      try { localStorage.setItem("health_context", JSON.stringify(ctx)); } catch { /* ignore */ }
      await submitContext(ctx);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Couldn't parse your message";
      setIntroError(/Not Found|404/i.test(msg) ? "API server not reachable. Is it running?" : msg);
    } finally {
      setIntroLoading(false);
    }
  };

  // ── Conversational refinement: add more info to existing context ──────────
  const handleRefine = async () => {
    if (!refineText.trim()) return;
    setRefineLoading(true);
    setRefineError(null);
    try {
      const parsed = await fetchContextFromText(refineText);
      const merged = mergeContexts(loadedCtx ?? {}, parsed);
      setLoadedCtx(merged);
      setRefineText("");
      setShowRefine(false);
      try { localStorage.setItem("health_context", JSON.stringify(merged)); } catch { /* ignore */ }
      await submitContext(merged);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Couldn't parse your update";
      setRefineError(/Not Found|404/i.test(msg) ? "API server not reachable." : msg);
    } finally {
      setRefineLoading(false);
    }
  };

  // ── Food chain ───────────────────────────────────────────────────────────
  const handleFoodChain = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!foodInput.trim()) return;
    setChainLoading(true);
    setChainData(null);
    try {
      setChainData(await fetchFoodChain(foodInput.trim()));
    } catch { /* silent */ } finally {
      setChainLoading(false);
    }
  };

  // ── Derived position (live preview from loaded context or map data) ───────
  const ctx = mapData?.profile ?? loadedCtx ?? {};
  const userX = mapData?.userX ?? ageToX(ctx.age);
  const userY = mapData?.userY ?? conditionsToY(ctx.conditions ?? [], ctx.symptoms ?? [], ctx.age);
  const { dx: destX, dy: destY } = destinationXY(userX, userY);

  const hasSubmitted = mapData !== null;
  const risks = mapData?.position.nearby_risks ?? [];
  const steps = mapData?.safestPath.steps ?? [];
  const earlySignals = mapData?.earlySignals.early_signals ?? [];
  const activeConditions = mapData?.position.active_conditions ?? (ctx.conditions ?? []);
  const activeSymptoms   = mapData?.position.active_symptoms   ?? (ctx.symptoms ?? []);

  const labelAge = ctx.age ? `${ctx.age}y` : "?";
  const labelGender = ctx.gender ? ` · ${ctx.gender}` : "";
  const markerLabel = `${labelAge}${labelGender}`;
  const zone = getZoneAt(userY);
  const narrative = buildNarrative(ctx.age, ctx.gender ?? null, activeConditions, activeSymptoms, userY, risks, steps);
  const refinePrompt = buildRefinePrompt(loadedCtx);

  const hasCtx = loadedCtx !== null;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-lg font-bold text-slate-900">Health Journey Map</h1>
            <p className="text-xs text-slate-500">Your personal health landscape — navigate toward your best health</p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/" className="text-slate-500 hover:text-slate-800">← Home</Link>
            <Link href="/kg" className="text-slate-500 hover:text-slate-800">KG Status</Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">

          {/* ── LEFT panel ───────────────────────────────────────────────── */}
          <div className="w-full lg:w-80 lg:flex-shrink-0 space-y-4">

            {/* ── CASE A: Context loaded from home page ──────────────────── */}
            {hasCtx ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Your Profile</h2>
                    {loading && (
                      <span className="text-xs text-blue-600 animate-pulse">Locating…</span>
                    )}
                    {hasSubmitted && !loading && (
                      <span className="text-xs text-emerald-600 font-medium">Map ready</span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Using info from your home profile.
                  </p>
                </div>

                {/* Profile chips */}
                <ProfileChips ctx={loadedCtx!} />

                {/* "Add more" toggle */}
                <button
                  type="button"
                  onClick={() => setShowRefine(v => !v)}
                  className="w-full rounded-lg border border-dashed border-slate-300 py-2 text-xs text-slate-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
                >
                  {showRefine ? "▲ Hide" : "▾ Tell me more — medications, goals, lifestyle…"}
                </button>

                {/* Conversational refinement input */}
                {showRefine && (
                  <div className="space-y-2">
                    <p className="text-xs text-slate-600 leading-relaxed">{refinePrompt}</p>
                    <textarea
                      value={refineText}
                      onChange={e => setRefineText(e.target.value)}
                      placeholder="e.g. I also take Metformin and try to walk 30 min a day. My goal is to sleep better."
                      rows={3}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:outline-none resize-none"
                    />
                    {refineError && <p className="text-xs text-red-600">{refineError}</p>}
                    <button
                      type="button"
                      onClick={handleRefine}
                      disabled={refineLoading || !refineText.trim()}
                      className="w-full rounded-xl bg-blue-600 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      {refineLoading ? "Updating map…" : "Update my map"}
                    </button>
                  </div>
                )}

                {error && <p className="text-xs text-red-600">{error}</p>}
              </div>
            ) : (
              /* ── CASE B: New user — chat-style intro ───────────────────── */
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                <div>
                  <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Tell Me About Yourself</h2>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                    Just type naturally — age, health conditions, symptoms, medications, goals. No need for a form.
                  </p>
                </div>
                <textarea
                  value={introText}
                  onChange={e => setIntroText(e.target.value)}
                  placeholder={`e.g. "I'm 48, female, have Type 2 diabetes and high blood pressure. I've been feeling tired lately and want to eat better."`}
                  rows={5}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:outline-none resize-none"
                />
                {introError && <p className="text-xs text-red-600">{introError}</p>}
                <button
                  type="button"
                  onClick={handleIntroSubmit}
                  disabled={introLoading || !introText.trim()}
                  className="w-full rounded-xl bg-blue-600 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {introLoading ? "Finding your position…" : "Show me my health map →"}
                </button>
                <p className="text-xs text-center text-slate-400">
                  Or go to <Link href="/" className="text-blue-500 hover:underline">Home</Link> for a full guided experience.
                </p>
              </div>
            )}

            {/* ── Zone indicator ─────────────────────────────────────────── */}
            {(hasCtx || hasSubmitted) && (
              <div className="rounded-2xl border-2 bg-white p-4 shadow-sm"
                style={{ borderColor: zone.hex }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: zone.hex }} />
                  <span className="text-sm font-bold" style={{ color: zone.hex }}>{zone.name}</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  <NarrativeText text={narrative} />
                </p>
              </div>
            )}

            {/* ── Safest path directions ──────────────────────────────────── */}
            {steps.length > 0 && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-wide text-emerald-700 mb-3">
                  Route Directions ({steps.length} steps)
                </h3>
                <ol className="space-y-2">
                  {steps.map((step, i) => (
                    <li key={i} className="flex gap-2.5">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                        style={{ backgroundColor: stepHex(step.action) }}>
                        {i + 1}
                      </span>
                      <div>
                        <p className="text-xs font-semibold text-slate-800">{step.action}</p>
                        {step.reason && (
                          <p className="text-xs text-slate-500 leading-snug mt-0.5">{step.reason}</p>
                        )}
                        {step.evidence?.length > 0 && (
                          <p className="text-xs text-emerald-600 mt-0.5">
                            {step.evidence.length} source{step.evidence.length !== 1 ? "s" : ""}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* ── Food-chain explorer ─────────────────────────────────────── */}
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600 mb-3">
                Food → Nutrient → Effect
              </h3>
              <form onSubmit={handleFoodChain} className="flex gap-2 mb-3">
                <input type="text" value={foodInput} onChange={e => setFoodInput(e.target.value)}
                  placeholder="e.g. Salmon, Spinach"
                  className="flex-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:border-violet-400 focus:outline-none" />
                <button type="submit" disabled={chainLoading || !foodInput.trim()}
                  className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50">
                  {chainLoading ? "…" : "Trace"}
                </button>
              </form>
              {chainData && <ChainPanel chain={chainData} />}
            </div>

            {/* ── Selected risk info ──────────────────────────────────────── */}
            {selectedRisk && (
              <InfoPanel risk={selectedRisk} onClose={() => setSelectedRisk(null)} />
            )}
          </div>

          {/* ── RIGHT: Map ───────────────────────────────────────────────── */}
          <div className="flex-1 min-w-0 space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 bg-slate-50">
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-green-500" /> Thriving</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Navigation</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-orange-400" /> Risk</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Critical</span>
                </div>
                <span className="text-xs text-slate-400">
                  {hasSubmitted ? "KG-enhanced position" : hasCtx ? "Loading position…" : "Enter your profile to navigate"}
                </span>
              </div>

              <svg viewBox={`0 0 ${W} ${H}`} className="w-full"
                style={{ aspectRatio: `${W}/${H}`, display: "block" }}>
                <MapBackground />

                {earlySignals.slice(0, 4).map((sig, i) => {
                  const { x, y } = riskXY(i + risks.length, userX, userY - 30);
                  return <WarningFlag key={i} x={x} y={y} label={sig.symptom} />;
                })}

                {(hasCtx || hasSubmitted) && (
                  <>
                    <SafeRoute ux={userX} uy={userY} dx={destX} dy={destY} />
                    <DestinationStar x={destX} y={destY} />
                  </>
                )}

                {risks.map((risk, i) => {
                  const { x, y } = riskXY(i, userX, userY);
                  return (
                    <RiskPin key={risk.name + i} x={x} y={y} sev={riskSev(risk)} label={risk.name}
                      selected={selectedRisk?.name === risk.name}
                      onClick={() => setSelectedRisk(selectedRisk?.name === risk.name ? null : risk)} />
                  );
                })}

                <UserMarker x={userX} y={userY} label={markerLabel || "You"} />
                <LifeRuler userX={userX} />
                <CompassRose cx={W - 30} cy={44} />
                <MapLegend />
              </svg>
            </div>

            {/* ── Risk grid ────────────────────────────────────────────── */}
            {risks.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-3">
                  Risk Zones Near You ({risks.length})
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {risks.map((risk, i) => {
                    const sev = riskSev(risk);
                    const isSelected = selectedRisk?.name === risk.name;
                    return (
                      <button key={i} type="button"
                        onClick={() => setSelectedRisk(isSelected ? null : risk)}
                        className={`text-left rounded-xl border-l-4 border border-slate-100 p-3 transition-all hover:shadow-md ${isSelected ? "ring-2 ring-offset-1" : ""}`}
                        style={{ borderLeftColor: SEV_HEX[sev], outlineColor: isSelected ? SEV_HEX[sev] : undefined }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-slate-800 truncate pr-2">{risk.name}</span>
                          <span className="text-xs font-bold rounded px-1.5 py-0.5 flex-shrink-0"
                            style={{ backgroundColor: SEV_GLOW[sev], color: SEV_HEX[sev] }}>
                            {sev.toUpperCase()}
                          </span>
                        </div>
                        {risk.reason && <p className="text-xs text-slate-500 leading-snug line-clamp-2">{risk.reason}</p>}
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 capitalize">{risk.kind}</span>
                          <span className="text-xs text-slate-400">{risk.evidence?.length ?? 0} source{risk.evidence?.length !== 1 ? "s" : ""}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Early signals ─────────────────────────────────────────── */}
            {earlySignals.length > 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
                <h3 className="text-xs font-bold uppercase tracking-wide text-amber-700 mb-3">
                  Early Signals — Watch These Indicators
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {earlySignals.map((sig, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="text-amber-500">⚑</span>
                      <span className="font-medium text-slate-800">{sig.symptom}</span>
                      <span className="text-slate-400">→</span>
                      <span className="text-amber-800">{sig.disease}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Empty state ───────────────────────────────────────────── */}
            {!hasSubmitted && !loading && (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-5 text-center">
                <p className="text-sm text-slate-500">
                  {hasCtx
                    ? "Loading your position from profile…"
                    : <>Fill in your profile on the left, or go to <Link href="/" className="text-blue-600 hover:underline">Home</Link> for the full guided experience.</>
                  }
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
