"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  fetchPosition, fetchSafestPath, fetchEarlySignals, fetchFoodChain,
  fetchContextFromText, fetchInterrogation, fetchLandmines,
  fetchPipelineStatus, triggerPipeline,
  saveSnapshot, fetchTrajectory,
} from "@/lib/api";
import type { FoodChainResponse, PipelineStatus } from "@/lib/api";
import type {
  UserContext, PositionResponse, SafestPathResponse,
  EarlySignalGuidanceResponse, NearbyRisk, PathStep, InterrogationResult,
  LandmineDisease, LandmineResult, Snapshot,
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

// ─── Health Journey math ─────────────────────────────────────────────────────
function computeHealthScore(y: number): number {
  return Math.round(100 * (1 - (y - 50) / (455 - 50)));
}

function scoreColor(score: number): string {
  if (score >= 75) return "#16a34a";
  if (score >= 45) return "#b45309";
  if (score >= 20) return "#dc2626";
  return "#7f1d1d";
}

interface SnapshotDiff {
  addedConditions: string[];
  removedConditions: string[];
  addedSymptoms: string[];
  removedSymptoms: string[];
}

function diffSnapshots(a: Snapshot, b: Snapshot): SnapshotDiff {
  return {
    addedConditions: b.conditions.filter(c => !a.conditions.includes(c)),
    removedConditions: a.conditions.filter(c => !b.conditions.includes(c)),
    addedSymptoms: b.symptoms.filter(s => !a.symptoms.includes(s)),
    removedSymptoms: a.symptoms.filter(s => !b.symptoms.includes(s)),
  };
}

// ─── Health Persona Types (MBTI-style, 12 archetypes) ────────────────────────
type PersonaZone = "V" | "G";
type PersonaComplexity = "S" | "C";
type PersonaMomentum = "A" | "S" | "D";
type PersonaCode = `${PersonaZone}${PersonaComplexity}${PersonaMomentum}`;

interface PersonaType {
  code: PersonaCode;
  name: string;
  color: string;
  descTemplate: string;
}

const PERSONA_CATALOG: Record<PersonaCode, PersonaType> = {
  VSA: { code: "VSA", name: "The Rising Star",        color: "#16a34a", descTemplate: "Score {score} with a clean health slate and upward momentum. You're building strong foundations." },
  VSS: { code: "VSS", name: "The Steady Beacon",      color: "#22c55e", descTemplate: "Score {score} in the vital zone — stable and simple. A solid baseline to build on." },
  VSD: { code: "VSD", name: "The Drifting Sail",       color: "#84cc16", descTemplate: "Score {score} but trending down. Few conditions, but something is shifting — worth paying attention." },
  VCA: { code: "VCA", name: "The Resilient Juggler",   color: "#0ea5e9", descTemplate: "Score {score} while managing {conditionCount} conditions and still climbing. Impressive resilience." },
  VCS: { code: "VCS", name: "The Balanced Navigator",  color: "#0284c7", descTemplate: "Score {score} holding steady with {conditionCount} conditions. You've found a working balance." },
  VCD: { code: "VCD", name: "The Watchful Guardian",   color: "#7c3aed", descTemplate: "Score {score} with {conditionCount} conditions and a downward drift. Time to reassess your strategy." },
  GSA: { code: "GSA", name: "The Climbing Scout",      color: "#f59e0b", descTemplate: "Score {score} in guarded territory, but you're climbing. Each step up matters." },
  GSS: { code: "GSS", name: "The Patient Walker",      color: "#d97706", descTemplate: "Score {score} — guarded zone, few conditions, holding position. Small changes can tip you upward." },
  GSD: { code: "GSD", name: "The Fading Ember",        color: "#ea580c", descTemplate: "Score {score} sliding down with {conditionCount} condition(s). This is your wake-up signal." },
  GCA: { code: "GCA", name: "The Phoenix Fighter",     color: "#dc2626", descTemplate: "Score {score} with {conditionCount} conditions, but you're fighting back. The hardest climbs earn the best views." },
  GCS: { code: "GCS", name: "The Storm Weatherer",     color: "#b91c1c", descTemplate: "Score {score} managing {conditionCount} conditions in guarded territory. Stability here is strength." },
  GCD: { code: "GCD", name: "The Critical Crossroads", color: "#7f1d1d", descTemplate: "Score {score} with {conditionCount} conditions and declining. This is the moment decisions matter most." },
};

function derivePersona(
  y: number, conditions: string[], snapshots: Snapshot[],
): { persona: PersonaType; zone: PersonaZone; complexity: PersonaComplexity; momentum: PersonaMomentum; score: number } {
  const score = computeHealthScore(y);
  const zone: PersonaZone = score >= 60 ? "V" : "G";
  const complexity: PersonaComplexity = conditions.length <= 1 ? "S" : "C";
  let momentum: PersonaMomentum = "S";
  const valid = snapshots.filter(s => s.position_y != null);
  if (valid.length >= 2) {
    const prev = computeHealthScore(valid[valid.length - 2].position_y!);
    const curr = computeHealthScore(valid[valid.length - 1].position_y!);
    const delta = curr - prev;
    if (delta > 2) momentum = "A";
    else if (delta < -2) momentum = "D";
  }
  const code = `${zone}${complexity}${momentum}` as PersonaCode;
  return { persona: PERSONA_CATALOG[code], zone, complexity, momentum, score };
}

// ─── Synthetic Health Bots ("People Like You") ──────────────────────────────
const BOT_NAMES = [
  "Alex", "Morgan", "Jordan", "Casey", "Riley", "Quinn",
  "Avery", "Taylor", "Sage", "River", "Rowan", "Parker",
];

const ESCALATION_MAP: Record<string, string> = {
  "Type 2 diabetes": "Chronic kidney disease",
  "Hypertension": "Cardiovascular disease",
  "High cholesterol": "Coronary artery disease",
  "Obesity": "Type 2 diabetes",
  "Chronic kidney disease": "End-stage renal disease",
  "Cardiovascular disease": "Heart failure",
  "Asthma": "COPD",
  "Depression": "Major depressive disorder",
  "Anxiety": "Panic disorder",
  "Sleep apnea": "Hypertension",
};

function profileHash(age: number | null | undefined, conditions: string[]): number {
  const str = `${age ?? 35}:${conditions.slice().sort().join(",")}`;
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

interface SyntheticBot {
  id: string;
  name: string;
  age: number;
  conditions: string[];
  symptoms: string[];
  role: "better" | "parallel" | "warning";
  color: string;
  trajectory: { x: number; y: number }[];
  currentX: number;
  currentY: number;
  score: number;
  description: string;
}

function generateBots(
  userAge: number | null | undefined,
  userConditions: string[],
  userSymptoms: string[],
): SyntheticBot[] {
  const age = userAge ?? 35;
  const hash = profileHash(age, userConditions);

  // Better Path bot
  const betterConds = userConditions.length > 0 ? userConditions.slice(0, -1) : [];
  const betterAge = Math.max(18, age - 2);
  const betterName = BOT_NAMES[hash % 12];
  const betterTrajectory: { x: number; y: number }[] = [];
  for (let step = 0; step < 5; step++) {
    const stepAge = betterAge - 4 + step;
    const stepConds = step < 2 ? [...betterConds, "Fatigue"] : betterConds;
    const stepSymps = step < 1 ? ["Fatigue"] : [];
    betterTrajectory.push({ x: ageToX(stepAge), y: conditionsToY(stepConds, stepSymps, stepAge) });
  }
  const betterCurrent = betterTrajectory[betterTrajectory.length - 1];

  // Parallel bot
  const parallelAge = age + (hash % 3 === 0 ? -1 : 1);
  const parallelName = BOT_NAMES[(hash + 4) % 12];
  const parallelTrajectory: { x: number; y: number }[] = [];
  for (let step = 0; step < 5; step++) {
    const stepAge = parallelAge - 4 + step;
    const wobbleConds = step === 2 ? [...userConditions, "Fatigue"] : userConditions;
    parallelTrajectory.push({ x: ageToX(stepAge), y: conditionsToY(wobbleConds, userSymptoms, stepAge) });
  }
  const parallelCurrent = parallelTrajectory[parallelTrajectory.length - 1];

  // Warning bot
  const warningAge = age + 2;
  const warningName = BOT_NAMES[(hash + 8) % 12];
  const lastCond = userConditions[userConditions.length - 1] ?? "";
  const escalated = ESCALATION_MAP[lastCond] ?? "Chronic fatigue";
  const warningConds = [...userConditions, escalated];
  const warningTrajectory: { x: number; y: number }[] = [];
  for (let step = 0; step < 5; step++) {
    const stepAge = warningAge - 4 + step;
    const stepConds = step < 2 ? userConditions : warningConds;
    const stepSymps = step >= 3 ? [...userSymptoms, "Fatigue"] : userSymptoms;
    warningTrajectory.push({ x: ageToX(stepAge), y: conditionsToY(stepConds, stepSymps, stepAge) });
  }
  const warningCurrent = warningTrajectory[warningTrajectory.length - 1];

  return [
    {
      id: "bot-better", name: betterName, age: betterAge,
      conditions: betterConds, symptoms: [], role: "better", color: "#16a34a",
      trajectory: betterTrajectory, currentX: betterCurrent.x, currentY: betterCurrent.y,
      score: computeHealthScore(betterCurrent.y), description: "Fewer conditions, improving",
    },
    {
      id: "bot-parallel", name: parallelName, age: parallelAge,
      conditions: userConditions, symptoms: userSymptoms, role: "parallel", color: "#6366f1",
      trajectory: parallelTrajectory, currentX: parallelCurrent.x, currentY: parallelCurrent.y,
      score: computeHealthScore(parallelCurrent.y), description: "Same landscape, holding steady",
    },
    {
      id: "bot-warning", name: warningName, age: warningAge,
      conditions: warningConds, symptoms: userSymptoms, role: "warning", color: "#dc2626",
      trajectory: warningTrajectory, currentX: warningCurrent.x, currentY: warningCurrent.y,
      score: computeHealthScore(warningCurrent.y), description: `Added ${escalated.toLowerCase()}, declining`,
    },
  ];
}

function destinationXY(userX: number, userY: number) {
  return { dx: Math.min(userX + 140, W - 55), dy: Math.max(userY - 138, 68) };
}

function nearTerritory(conditions: string[]): string {
  const t = conditions.join(" ").toLowerCase();
  if (/diabetes|blood sugar|insulin|glucose|metabolic/.test(t)) return "Metabolic Crossroads";
  if (/hypertension|heart|cardiovascular|cholesterol|pressure/.test(t)) return "Cardiometabolic Ridge";
  if (/inflamm|arthritis|autoimmune|lupus|depression|mood/.test(t)) return "Inflammatory Plains";
  if (/sarcopenia|osteoporosis|muscle|bone|joint/.test(t)) return "Musculoskeletal Valley";
  if (/neuro|cognitive|alzheimer|parkinson|dementia/.test(t)) return "Neurological Frontier";
  if (/stroke|cerebro|brain ischemia/.test(t)) return "Recovery Valley";
  if (/kidney|renal|ckd/.test(t)) return "Metabolic Crossroads";
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

// Landmine early warning signs that, if present in symptoms, warrant a map mention
const LANDMINE_SIGNAL_SYMPTOMS = new Set([
  "Memory loss", "Brain fog", "Confusion",
  "TIA (mini-stroke)", "Uncontrolled blood pressure",
  "Shortness of breath on exertion", "Palpitations",
  "Fatigue", "Swollen ankles/feet", "Foamy urine",
  "Upper abdominal pain", "Unexplained weight loss",
  "Persistent low mood", "Social withdrawal", "Sleep disturbance",
]);

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

  // Landmine warning signs confirmed
  const confirmedSignals = symptoms.filter(s => LANDMINE_SIGNAL_SYMPTOMS.has(s));
  if (confirmedSignals.length > 0) {
    t += ` **Early warning signs detected** (${confirmedSignals.join(", ")}) — check the landmine markers on your map.`;
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
        <linearGradient id="g-trajectory" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.85" />
        </linearGradient>
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

function BotGhostMarker({ x, y, color, name, personaCode }: {
  x: number; y: number; color: string; name: string; personaCode: string;
}) {
  return (
    <g opacity="0.45">
      <circle cx={x} cy={y} r={6} fill={color} stroke="white" strokeWidth="1.5" />
      <circle cx={x} cy={y} r={2} fill="white" />
      <text x={x} y={y + 14} textAnchor="middle"
        style={{ fontSize: "6.5px", fill: color, fontWeight: "600", userSelect: "none" }}>
        {name} · {personaCode}
      </text>
    </g>
  );
}

function BotTrajectoryTrail({ points, color }: {
  points: { x: number; y: number }[]; color: string;
}) {
  if (points.length < 2) return null;
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x},${p.y}`).join(" ");
  return (
    <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeOpacity="0.35"
      strokeDasharray="4,4" strokeLinecap="round" strokeLinejoin="round" />
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
    { color: "#dc2626", label: "Landmine disease", mine: true },
  ];
  const LX = 14, LY = H - 162;
  return (
    <g>
      <rect x={LX - 6} y={LY - 14} width={132} height={items.length * 17 + 18}
        rx={6} fill="white" fillOpacity="0.88" stroke="#cbd5e1" strokeWidth="1" />
      <text x={LX + 55} y={LY} textAnchor="middle"
        style={{ fontSize: "8px", fill: "#475569", fontWeight: "700", letterSpacing: "0.06em" }}>
        LEGEND
      </text>
      {items.map(({ color, label, mine }, i) => (
        <g key={label} transform={`translate(${LX}, ${LY + 10 + i * 17})`}>
          {mine ? (
            <g transform="translate(0,-3)">
              <circle r={4} fill={color} />
              {[0,45,90,135,180,225,270,315].map((a, si) => {
                const rad = a * Math.PI / 180;
                return <line key={si} x1={Math.cos(rad)*4} y1={Math.sin(rad)*4}
                  x2={Math.cos(rad)*7} y2={Math.sin(rad)*7}
                  stroke={color} strokeWidth="1.2" />;
              })}
            </g>
          ) : (
            <circle cy={-3} r={5} fill={color} />
          )}
          <text x={12} style={{ fontSize: "8px", fill: "#475569" }}>{label}</text>
        </g>
      ))}
    </g>
  );
}

// ─── Health Journey components ───────────────────────────────────────────────

function HealthScoreGauge({ score }: { score: number }) {
  const [displayScore, setDisplayScore] = useState(0);
  useEffect(() => {
    const target = score;
    const duration = 1200;
    const startTime = performance.now();
    let raf: number;
    function tick(now: number) {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayScore(Math.round(eased * target));
      if (progress < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score]);

  const R = 40, cx = 50, cy = 50;
  const circumference = 2 * Math.PI * R;
  const arcLen = (270 / 360) * circumference;
  const fillLen = arcLen * (Math.max(0, Math.min(100, score)) / 100);
  const color = scoreColor(score);

  return (
    <svg viewBox="0 0 100 100" className="w-28 h-28 mx-auto">
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="#e2e8f0" strokeWidth="7"
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeLinecap="round" transform={`rotate(135 ${cx} ${cy})`} />
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={color} strokeWidth="7"
        strokeDasharray={`${arcLen} ${circumference}`}
        strokeDashoffset={arcLen - fillLen}
        strokeLinecap="round" transform={`rotate(135 ${cx} ${cy})`}>
        <animate attributeName="stroke-dashoffset" from={String(arcLen)} to={String(arcLen - fillLen)}
          dur="1.2s" fill="freeze" />
      </circle>
      <text x={cx} y={cy - 2} textAnchor="middle" dominantBaseline="central"
        style={{ fontSize: "20px", fontWeight: 800, fill: color }}>{displayScore}</text>
      <text x={cx} y={cy + 14} textAnchor="middle"
        style={{ fontSize: "7px", fill: "#64748b", fontWeight: 600 }}>Health Score</text>
    </svg>
  );
}

function TrajectorySparkline({ snapshots }: { snapshots: Snapshot[] }) {
  const pts = snapshots
    .filter(s => s.position_y != null && s.recorded_at)
    .map(s => ({ score: computeHealthScore(s.position_y!), time: new Date(s.recorded_at).getTime() }));
  if (pts.length < 2) return null;

  const SW = 260, SH = 80, PAD = 12;
  const plotW = SW - PAD * 2, plotH = SH - PAD * 2;
  const minT = pts[0].time, maxT = pts[pts.length - 1].time;
  const tRange = maxT - minT || 1;
  const points = pts.map(p => ({
    x: PAD + ((p.time - minT) / tRange) * plotW,
    y: PAD + plotH - (Math.max(0, Math.min(100, p.score)) / 100) * plotH,
    score: p.score,
  }));

  let pathD = `M ${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const cpx = (points[i - 1].x + points[i].x) / 2;
    pathD += ` Q ${cpx},${points[i - 1].y} ${points[i].x},${points[i].y}`;
  }
  const areaD = pathD + ` L ${points[points.length - 1].x},${PAD + plotH} L ${points[0].x},${PAD + plotH} Z`;
  const color = scoreColor(pts[pts.length - 1].score);
  const fmtDate = (ts: number) => new Date(ts).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  const bands = [
    { y1: 0, y2: 20, color: "#7f1d1d" },
    { y1: 20, y2: 45, color: "#dc2626" },
    { y1: 45, y2: 75, color: "#b45309" },
    { y1: 75, y2: 100, color: "#16a34a" },
  ];

  return (
    <svg viewBox={`0 0 ${SW} ${SH}`} className="w-full">
      <defs>
        <linearGradient id="spark-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {bands.map((b, i) => (
        <rect key={i} x={PAD} y={PAD + plotH - (b.y2 / 100) * plotH}
          width={plotW} height={((b.y2 - b.y1) / 100) * plotH}
          fill={b.color} opacity="0.08" />
      ))}
      <path d={areaD} fill="url(#spark-area)" />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
      {points.map((p, i) => (
        <g key={i}>
          {i === points.length - 1 && (
            <circle cx={p.x} cy={p.y} r={4} fill={scoreColor(p.score)} fillOpacity="0">
              <animate attributeName="r" from="3" to="8" dur="1.5s" repeatCount="indefinite" />
              <animate attributeName="fill-opacity" from="0.4" to="0" dur="1.5s" repeatCount="indefinite" />
            </circle>
          )}
          <circle cx={p.x} cy={p.y} r={i === points.length - 1 ? 3.5 : 2.5}
            fill={scoreColor(p.score)} stroke="white" strokeWidth="1" />
        </g>
      ))}
      <text x={points[0].x} y={SH - 1} textAnchor="start"
        style={{ fontSize: "7px", fill: "#94a3b8" }}>{fmtDate(minT)}</text>
      <text x={points[points.length - 1].x} y={SH - 1} textAnchor="end"
        style={{ fontSize: "7px", fill: "#94a3b8" }}>{fmtDate(maxT)}</text>
    </svg>
  );
}

function TrajectoryPath({ snapshots }: { snapshots: Snapshot[] }) {
  const pts = snapshots
    .filter(s => s.position_x != null && s.position_y != null)
    .map(s => ({ x: s.position_x!, y: s.position_y!, zone: s.zone, recorded_at: s.recorded_at }));
  if (pts.length < 2) return null;

  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x},${p.y}`).join(" ");
  const totalLen = pts.reduce((sum, p, i) => {
    if (i === 0) return 0;
    return sum + Math.sqrt((p.x - pts[i - 1].x) ** 2 + (p.y - pts[i - 1].y) ** 2);
  }, 0);
  const fmtDate = (d: string) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <g>
      <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="4" strokeOpacity="0.15"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d={pathD} fill="none" stroke="url(#g-trajectory)" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round"
        strokeDasharray={totalLen} strokeDashoffset={totalLen}>
        <animate attributeName="stroke-dashoffset" from={String(totalLen)} to="0"
          dur="2s" fill="freeze" />
      </path>
      {pts.map((p, i) => {
        const isTransition = i > 0 && p.zone !== pts[i - 1].zone;
        if (i === pts.length - 1) return null;
        return isTransition ? (
          <g key={i} transform={`translate(${p.x},${p.y})`}>
            <polygon points="0,-5 5,0 0,5 -5,0" fill="#6366f1" stroke="white" strokeWidth="1.5" />
          </g>
        ) : (
          <circle key={i} cx={p.x} cy={p.y} r={2.5}
            fill="#6366f1" opacity={0.3 + (i / pts.length) * 0.5}
            stroke="white" strokeWidth="0.5" />
        );
      })}
      <text x={pts[0].x} y={pts[0].y + 14} textAnchor="middle"
        style={{ fontSize: "6.5px", fill: "#6366f1", opacity: 0.7 }}>{fmtDate(pts[0].recorded_at)}</text>
      <text x={pts[pts.length - 1].x} y={pts[pts.length - 1].y + 14} textAnchor="middle"
        style={{ fontSize: "6.5px", fill: "#6366f1", opacity: 0.7 }}>{fmtDate(pts[pts.length - 1].recorded_at)}</text>
    </g>
  );
}

function DriftIndicator({ snapshots }: { snapshots: Snapshot[] }) {
  const valid = snapshots.filter(s => s.position_y != null);
  if (valid.length < 2) return null;

  const prev = valid[valid.length - 2];
  const curr = valid[valid.length - 1];
  const prevScore = computeHealthScore(prev.position_y!);
  const currScore = computeHealthScore(curr.position_y!);
  const delta = currScore - prevScore;

  const prevZone = prev.zone ?? getZoneAt(prev.position_y!).name;
  const currZone = curr.zone ?? getZoneAt(curr.position_y!).name;
  const zoneChanged = prevZone !== currZone;

  const direction = delta > 2 ? "improving" : delta < -2 ? "worsening" : "steady";
  const arrow = direction === "improving" ? "\u25B2" : direction === "worsening" ? "\u25BC" : "\u25B6";
  const arrowColor = direction === "improving" ? "#16a34a" : direction === "worsening" ? "#dc2626" : "#94a3b8";
  const deltaStr = delta > 0 ? `+${delta}` : String(delta);
  const fmtDate = (s: Snapshot) => new Date(s.recorded_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const shortZone = (z: string) => {
    if (z.includes("Thriving")) return "Thriving";
    if (z.includes("Navigation")) return "Navigation";
    if (z.includes("Risk")) return "Risk";
    return "Critical";
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold" style={{ color: arrowColor }}>{arrow}</span>
        <span className="text-sm font-bold" style={{ color: arrowColor }}>{deltaStr}</span>
        <span className="text-xs text-slate-500">
          {direction === "improving" ? "Improving" : direction === "worsening" ? "Worsening" : "Steady"}
          {" \u00B7 since "}{fmtDate(prev)}
        </span>
      </div>
      {zoneChanged && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="rounded-full px-2 py-0.5 font-semibold text-white"
            style={{ backgroundColor: scoreColor(prevScore) }}>{shortZone(prevZone)}</span>
          <span className="text-slate-400">{"\u2192"}</span>
          <span className="rounded-full px-2 py-0.5 font-semibold text-white"
            style={{ backgroundColor: scoreColor(currScore) }}>{shortZone(currZone)}</span>
        </div>
      )}
    </div>
  );
}

function ZoneTransitionBadges({ snapshots }: { snapshots: Snapshot[] }) {
  const valid = snapshots.filter(s => s.position_y != null && s.zone);
  if (valid.length < 2) return null;

  const transitions: { zone: string; date: string; score: number }[] = [
    { zone: valid[0].zone!, date: valid[0].recorded_at, score: computeHealthScore(valid[0].position_y!) },
  ];
  for (let i = 1; i < valid.length; i++) {
    if (valid[i].zone !== valid[i - 1].zone) {
      transitions.push({ zone: valid[i].zone!, date: valid[i].recorded_at, score: computeHealthScore(valid[i].position_y!) });
    }
  }
  const last = valid[valid.length - 1];
  if (transitions[transitions.length - 1].date !== last.recorded_at) {
    transitions.push({ zone: last.zone!, date: last.recorded_at, score: computeHealthScore(last.position_y!) });
  }
  if (transitions.length < 2) return null;

  const abbrev = (z: string) => {
    if (z.includes("Thriving")) return "THR";
    if (z.includes("Navigation")) return "NAV";
    if (z.includes("Risk")) return "RISK";
    return "CRIT";
  };
  const zoneHex = (z: string) => {
    if (z.includes("Thriving")) return "#16a34a";
    if (z.includes("Navigation")) return "#b45309";
    if (z.includes("Risk")) return "#dc2626";
    return "#7f1d1d";
  };
  const fmtDate = (d: string) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  return (
    <div className="flex items-center gap-0 overflow-x-auto">
      {transitions.map((t, i) => (
        <div key={i} className="flex items-center">
          {i > 0 && <div className="w-4 h-0.5" style={{ backgroundColor: zoneHex(transitions[i - 1].zone), opacity: 0.4 }} />}
          <div className="flex flex-col items-center">
            <span className="rounded-full px-2 py-0.5 text-xs font-bold text-white"
              style={{ backgroundColor: zoneHex(t.zone) }}>{abbrev(t.zone)}</span>
            <span className="text-slate-400 mt-0.5" style={{ fontSize: "7px" }}>{fmtDate(t.date)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ConditionDiff({ snapshots }: { snapshots: Snapshot[] }) {
  const valid = snapshots.filter(s => s.position_y != null);
  if (valid.length < 2) return <p className="text-xs text-slate-400 italic">No prior visits to compare</p>;

  const diff = diffSnapshots(valid[valid.length - 2], valid[valid.length - 1]);
  const hasChanges = diff.addedConditions.length + diff.removedConditions.length +
                     diff.addedSymptoms.length + diff.removedSymptoms.length > 0;
  if (!hasChanges) return <p className="text-xs text-slate-400 italic">No changes since last visit</p>;

  return (
    <div className="space-y-1">
      {diff.addedConditions.map(c => (
        <div key={`+c:${c}`} className="flex items-center gap-1.5 text-xs">
          <span className="rounded-full bg-red-100 text-red-700 px-1.5 py-0.5 font-bold">+</span>
          <span className="text-slate-700">{c}</span>
        </div>
      ))}
      {diff.removedConditions.map(c => (
        <div key={`-c:${c}`} className="flex items-center gap-1.5 text-xs">
          <span className="rounded-full bg-green-100 text-green-700 px-1.5 py-0.5 font-bold">{"\u2212"}</span>
          <span className="text-slate-500 line-through">{c}</span>
        </div>
      ))}
      {diff.addedSymptoms.map(s => (
        <div key={`+s:${s}`} className="flex items-center gap-1.5 text-xs">
          <span className="rounded-full bg-orange-100 text-orange-700 px-1.5 py-0.5 font-bold">+</span>
          <span className="text-slate-600">{s}</span>
        </div>
      ))}
      {diff.removedSymptoms.map(s => (
        <div key={`-s:${s}`} className="flex items-center gap-1.5 text-xs">
          <span className="rounded-full bg-slate-100 text-slate-500 px-1.5 py-0.5 font-bold">{"\u2212"}</span>
          <span className="text-slate-400 line-through">{s}</span>
        </div>
      ))}
    </div>
  );
}

function JourneyPanel({ trajectory, currentY }: { trajectory: Snapshot[]; currentY: number }) {
  if (trajectory.length === 0) return null;
  const score = computeHealthScore(currentY);

  if (trajectory.length === 1) {
    return (
      <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-4 shadow-sm space-y-3 dark:border-indigo-800 dark:bg-indigo-900/20">
        <h3 className="text-xs font-bold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">Your Health Journey</h3>
        <HealthScoreGauge score={score} />
        <p className="text-xs text-center text-slate-500 italic dark:text-gray-400">Come back to track your journey</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-4 shadow-sm space-y-3 dark:border-indigo-800 dark:bg-indigo-900/20">
      <h3 className="text-xs font-bold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">Your Health Journey</h3>
      <HealthScoreGauge score={score} />
      <DriftIndicator snapshots={trajectory} />
      <TrajectorySparkline snapshots={trajectory} />
      <ZoneTransitionBadges snapshots={trajectory} />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">What Changed</p>
        <ConditionDiff snapshots={trajectory} />
      </div>
    </div>
  );
}

// ─── Health Persona Card ─────────────────────────────────────────────────────
function HealthPersonaCard({ persona, zone, complexity, momentum, score, conditionCount }: {
  persona: PersonaType; zone: PersonaZone; complexity: PersonaComplexity;
  momentum: PersonaMomentum; score: number; conditionCount: number;
}) {
  const desc = persona.descTemplate
    .replace("{score}", String(score))
    .replace("{conditionCount}", String(conditionCount))
    .replace("{zone}", zone === "V" ? "vital zone" : "guarded zone");

  const dimLabel = (dim: string, val: string) => {
    if (dim === "zone") return val === "V" ? "Vital" : "Guarded";
    if (dim === "complexity") return val === "S" ? "Simple" : "Complex";
    return val === "A" ? "Ascending" : val === "D" ? "Declining" : "Steady";
  };

  return (
    <div className="rounded-2xl border bg-white p-4 shadow-sm space-y-2.5 dark:bg-gray-800"
      style={{ borderColor: persona.color + "60" }}>
      <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-gray-500">Your Health Persona</p>
      <div className="flex items-center gap-3">
        <span className="rounded-lg px-2.5 py-1.5 text-sm font-black text-white"
          style={{ backgroundColor: persona.color }}>{persona.code}</span>
        <span className="text-sm font-bold text-slate-800 dark:text-gray-100">{persona.name}</span>
      </div>
      <div className="flex gap-1.5">
        {[
          { label: dimLabel("zone", zone) },
          { label: dimLabel("complexity", complexity) },
          { label: dimLabel("momentum", momentum) },
        ].map(({ label }) => (
          <span key={label} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300">
            {label}
          </span>
        ))}
      </div>
      <p className="text-xs text-slate-600 leading-relaxed italic dark:text-gray-300">{"\u201C"}{desc}{"\u201D"}</p>
    </div>
  );
}

// ─── Bot Panel ───────────────────────────────────────────────────────────────
const BOT_ROLE_COLORS: Record<string, string> = { better: "#16a34a", parallel: "#6366f1", warning: "#dc2626" };

function BotPanel({ bots, showBots, onToggle, trajectory }: {
  bots: SyntheticBot[]; showBots: boolean; onToggle: () => void; trajectory: Snapshot[];
}) {
  if (bots.length === 0) return null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-3 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-gray-500">People Like You</p>
        <button type="button" onClick={onToggle}
          className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-colors dark:border-gray-600 dark:text-gray-400 dark:hover:border-blue-500 dark:hover:text-blue-400">
          {showBots ? "Hide" : "Show on map"}
        </button>
      </div>
      {bots.map((bot) => {
        const botPersona = derivePersona(bot.currentY, bot.conditions, trajectory);
        return (
          <div key={bot.id} className="flex items-start gap-2.5">
            <span className="mt-1 inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: BOT_ROLE_COLORS[bot.role] ?? "#94a3b8" }} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs font-bold text-slate-800 dark:text-gray-100">{bot.name}</span>
                <span className="text-xs text-slate-500 dark:text-gray-400">({bot.age})</span>
                <span className="rounded-full px-1.5 py-0.5 font-bold text-white"
                  style={{ backgroundColor: botPersona.persona.color, fontSize: "9px" }}>
                  {botPersona.persona.code}
                </span>
                <span className="text-xs text-slate-500 dark:text-gray-400">Score {bot.score}</span>
              </div>
              <p className="text-xs text-slate-500 italic mt-0.5 dark:text-gray-400">{"\u201C"}{bot.description}{"\u201D"}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Health ID Badge ─────────────────────────────────────────────────────────
function HealthIdBadge({ token, onRestore }: {
  token: string; onRestore: (newToken: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [showRestore, setShowRestore] = useState(false);
  const [restoreInput, setRestoreInput] = useState("");

  const shortId = token.slice(-8);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard API may fail in some contexts */ }
  };

  const handleRestore = () => {
    const trimmed = restoreInput.trim();
    if (trimmed) {
      onRestore(trimmed);
      setRestoreInput("");
      setShowRestore(false);
    }
  };

  if (!token) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2 dark:border-gray-700 dark:bg-gray-800">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-400 dark:text-gray-500">Your Health ID</p>
      <div className="flex items-center gap-2">
        <span className="rounded-md bg-white border border-slate-200 px-2.5 py-1 text-xs font-mono font-bold text-slate-700 tracking-wider dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200">
          {shortId}
        </span>
        <button type="button" onClick={handleCopy}
          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-colors dark:border-gray-600 dark:bg-gray-700 dark:text-gray-400 dark:hover:border-blue-500 dark:hover:text-blue-400">
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <p className="text-xs text-slate-400 leading-snug dark:text-gray-500">
        Saved anonymously on this device. Copy ID to restore elsewhere.
      </p>
      <button type="button" onClick={() => setShowRestore(v => !v)}
        className="text-xs text-slate-500 hover:text-blue-600 transition-colors dark:text-gray-400 dark:hover:text-blue-400">
        {showRestore ? "\u25BE Hide restore" : "\u25B8 Restore from another device"}
      </button>
      {showRestore && (
        <div className="flex gap-2">
          <input type="text" value={restoreInput} onChange={e => setRestoreInput(e.target.value)}
            placeholder="Paste your Health ID"
            onKeyDown={e => { if (e.key === "Enter") handleRestore(); }}
            className="flex-1 rounded-md border border-slate-200 px-2 py-1 text-xs font-mono focus:border-blue-400 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:placeholder-gray-500" />
          <button type="button" onClick={handleRestore}
            disabled={!restoreInput.trim()}
            className="rounded-md bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors">
            Restore
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Landmine colors ──────────────────────────────────────────────────────────
const MINE_COLORS: Record<string, { fill: string; glow: string; opacity: number }> = {
  none:   { fill: "#94a3b8", glow: "#e2e8f0", opacity: 0.25 },
  low:    { fill: "#d97706", glow: "#fde68a", opacity: 0.75 },
  medium: { fill: "#ea580c", glow: "#fdba74", opacity: 0.9  },
  high:   { fill: "#dc2626", glow: "#fca5a5", opacity: 1.0  },
};

function LandmineMarker({
  x, y, riskLevel, name, korean, selected, onClick,
}: {
  x: number; y: number; riskLevel: string; name: string; korean: string;
  selected: boolean; onClick: () => void;
}) {
  const mc = MINE_COLORS[riskLevel] ?? MINE_COLORS.none;
  const spikes = [0, 45, 90, 135, 180, 225, 270, 315];
  const isPulsing = riskLevel === "medium" || riskLevel === "high";
  const scale = selected ? 1.3 : 1.0;
  const shortName = name.length > 16 ? name.slice(0, 15) + "…" : name;

  return (
    <g onClick={onClick} style={{ cursor: "pointer" }}
      transform={`translate(${x},${y}) scale(${scale})`}
      opacity={mc.opacity}>
      {isPulsing && (
        <circle r={14} fill={mc.glow}>
          <animate attributeName="r" from="10" to="18" dur={riskLevel === "high" ? "1.2s" : "2s"} repeatCount="indefinite" />
          <animate attributeName="opacity" from="0.5" to="0" dur={riskLevel === "high" ? "1.2s" : "2s"} repeatCount="indefinite" />
        </circle>
      )}
      {selected && <circle r={16} fill={mc.glow} opacity="0.6" />}
      {/* Mine body */}
      <circle r={7} fill={mc.fill} stroke="white" strokeWidth="1.5" />
      <circle r={2.5} fill="white" opacity="0.7" />
      {/* Spikes */}
      {spikes.map((angle) => {
        const rad = angle * Math.PI / 180;
        return (
          <line key={angle}
            x1={Math.cos(rad) * 7} y1={Math.sin(rad) * 7}
            x2={Math.cos(rad) * 12} y2={Math.sin(rad) * 12}
            stroke={mc.fill} strokeWidth="2" strokeLinecap="round" />
        );
      })}
      {/* Label */}
      <text y={22} textAnchor="middle"
        style={{ fontSize: "6.5px", fill: mc.fill, fontWeight: "700", userSelect: "none" }}>
        {shortName}
      </text>
      <text y={30} textAnchor="middle"
        style={{ fontSize: "6px", fill: "#64748b", userSelect: "none" }}>
        {korean}
      </text>
    </g>
  );
}

// ─── Landmine detail panel ────────────────────────────────────────────────────
const RISK_BADGE: Record<string, string> = {
  none:   "bg-slate-100 text-slate-500",
  low:    "bg-amber-100 text-amber-700",
  medium: "bg-orange-100 text-orange-700",
  high:   "bg-red-100 text-red-700",
};
const RISK_LABEL: Record<string, string> = {
  none: "No current risk factors", low: "Low risk", medium: "Elevated risk", high: "High risk",
};
const RISK_BORDER: Record<string, string> = {
  none: "#94a3b8", low: "#d97706", medium: "#ea580c", high: "#dc2626",
};

function LandminePanel({ landmine, onClose }: { landmine: LandmineDisease; onClose: () => void }) {
  const borderColor = RISK_BORDER[landmine.risk_level] ?? "#94a3b8";
  return (
    <div className="relative rounded-xl border-2 bg-white p-4 shadow-lg space-y-3 dark:bg-gray-800"
      style={{ borderColor }}>
      <button onClick={onClose}
        className="absolute right-3 top-3 text-slate-400 hover:text-slate-700 text-lg leading-none dark:text-gray-500 dark:hover:text-gray-300">×</button>

      {/* Header */}
      <div className="flex items-start gap-2 pr-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-slate-900 dark:text-gray-100">{landmine.name}</h3>
            <span className="text-slate-500 text-sm dark:text-gray-400">({landmine.korean})</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${RISK_BADGE[landmine.risk_level]}`}>
              {RISK_LABEL[landmine.risk_level]}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 italic dark:text-gray-400">{landmine.territory}</p>
        </div>
      </div>

      {/* Why critical */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-700 leading-relaxed dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200">
        <span className="font-semibold text-slate-800 dark:text-gray-100">Why this is a landmine: </span>
        {landmine.why_critical}
      </div>

      {/* Risk factors */}
      {(landmine.risk_factors_present.length > 0 || landmine.risk_factors_missing.length > 0) && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5 dark:text-gray-500">Risk factors</p>
          <div className="space-y-1">
            {landmine.risk_factors_present.map((rf, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-red-500 font-bold">✗</span>
                <span className="text-red-700 font-medium dark:text-red-400">{rf}</span>
              </div>
            ))}
            {landmine.risk_factors_missing.slice(0, 4).map((rf, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-emerald-500">✓</span>
                <span className="text-slate-500 dark:text-gray-400">{rf}</span>
              </div>
            ))}
            {landmine.risk_factors_missing.length > 4 && (
              <p className="text-xs text-slate-400 dark:text-gray-500">+{landmine.risk_factors_missing.length - 4} more not present</p>
            )}
          </div>
        </div>
      )}

      {/* Early warning signs */}
      {landmine.early_warning_signs.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5 dark:text-gray-500">Early warning signs</p>
          <div className="flex flex-wrap gap-1">
            {landmine.early_warning_signs.map((sign, i) => (
              <span key={i} className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-300">
                {sign}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Escape routes */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5 dark:text-gray-500">
          Escape routes {landmine.kg_evidence.length > 0 && (
            <span className="rounded-full bg-emerald-100 text-emerald-700 px-1.5 py-0.5 text-xs ml-1 normal-case font-normal dark:bg-emerald-900/20 dark:text-emerald-400">
              {landmine.kg_evidence.length} KG sources
            </span>
          )}
        </p>
        <div className="space-y-1">
          {landmine.escape_routes.slice(0, 4).map((route, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="text-emerald-500 mt-0.5">→</span>
              <span className="text-slate-700 dark:text-gray-200">{route}</span>
              {landmine.kg_evidence[i] && (
                <span className="ml-auto rounded px-1 py-0.5 text-xs bg-blue-50 text-blue-600 flex-shrink-0 dark:bg-blue-900/20 dark:text-blue-400">
                  {landmine.kg_evidence[i].predicate}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
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
    <div className="relative rounded-xl border-2 bg-white p-4 shadow-lg dark:bg-gray-800"
      style={{ borderColor: SEV_HEX[sev] }}>
      <button onClick={onClose}
        className="absolute right-3 top-3 text-slate-400 hover:text-slate-700 text-lg leading-none dark:text-gray-500 dark:hover:text-gray-300">×</button>
      <div className="flex items-center gap-2 mb-2">
        <span className="h-3 w-3 rounded-full" style={{ backgroundColor: SEV_HEX[sev] }} />
        <h3 className="font-bold text-slate-900 dark:text-gray-100">{risk.name}</h3>
        <span className="rounded px-1.5 py-0.5 text-xs font-bold text-white"
          style={{ backgroundColor: SEV_HEX[sev] }}>{sev.toUpperCase()}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 capitalize dark:bg-gray-700 dark:text-gray-300">{risk.kind}</span>
      </div>
      {risk.reason && <p className="text-sm text-slate-700 mb-3 leading-relaxed dark:text-gray-200">{risk.reason}</p>}
      {risk.evidence?.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5 dark:text-gray-500">
            Evidence ({risk.evidence.length} source{risk.evidence.length !== 1 ? "s" : ""})
          </p>
          <div className="space-y-1.5">
            {risk.evidence.slice(0, 3).map((ev, i) => (
              <div key={i} className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs dark:border-gray-600 dark:bg-gray-700">
                <span className={`inline-block rounded px-1 py-0.5 text-xs font-medium mr-1 ${
                  ev.source_type === "FDA" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                }`}>{ev.source_type || "PMC"}</span>
                <span className="font-mono text-slate-600 dark:text-gray-300">{ev.source_id}</span>
                {ev.journal && <span className="ml-1 italic text-slate-500 dark:text-gray-400">{ev.journal}</span>}
                {ev.context && <p className="mt-1 text-slate-500 dark:text-gray-400">"{ev.context}"</p>}
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
    <div className="rounded-xl border border-violet-200 bg-violet-50 p-4 dark:border-violet-800 dark:bg-violet-900/20">
      <div className="flex items-center gap-2 mb-3">
        <span className="font-bold text-violet-900 text-base dark:text-violet-300">{chain.food}</span>
        <span className="text-xs text-slate-500 dark:text-gray-400">{chain.chain.length} chain links</span>
      </div>
      {chain.chain.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-gray-400">No chains found in the KG for this food.</p>
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

// ─── Interrogation panel ─────────────────────────────────────────────────────
const SEV_INSIGHT: Record<string, string> = {
  high: "border-red-200 bg-red-50 text-red-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

const LM_CHECK_BORDER: Record<string, string> = {
  high: "border-red-300 bg-red-50/80",
  medium: "border-orange-300 bg-orange-50/80",
  low: "border-amber-200 bg-amber-50/60",
  none: "border-slate-200 bg-slate-50",
};
const LM_CHECK_BTN_YES: Record<string, string> = {
  high: "bg-red-600 hover:bg-red-700 text-white",
  medium: "bg-orange-500 hover:bg-orange-600 text-white",
  low: "bg-amber-500 hover:bg-amber-600 text-white",
  none: "bg-slate-500 hover:bg-slate-600 text-white",
};

// Mine SVG icon (inline, small)
function MineSvg({ color = "#dc2626", size = 14 }: { color?: string; size?: number }) {
  const spikes = [0, 45, 90, 135, 180, 225, 270, 315];
  const r = size / 2;
  return (
    <svg width={size + 6} height={size + 6} viewBox={`-${r+3} -${r+3} ${size+6} ${size+6}`} style={{ display: "inline-block", verticalAlign: "middle" }}>
      <circle r={r} fill={color} />
      <circle r={r * 0.35} fill="white" opacity="0.7" />
      {spikes.map(a => {
        const rad = a * Math.PI / 180;
        return <line key={a} x1={Math.cos(rad)*r} y1={Math.sin(rad)*r}
          x2={Math.cos(rad)*(r+3)} y2={Math.sin(rad)*(r+3)}
          stroke={color} strokeWidth="1.5" strokeLinecap="round" />;
      })}
    </svg>
  );
}

function CompletenessBar({ score, checksRemaining }: { score: number; checksRemaining?: number }) {
  const color = score >= 80 ? "#16a34a" : score >= 50 ? "#b45309" : "#dc2626";
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-slate-600">Assessment completeness</span>
        <div className="flex items-center gap-2">
          {(checksRemaining ?? 0) > 0 && (
            <span className="rounded-full bg-orange-100 text-orange-700 px-2 py-0.5 text-xs font-medium">
              {checksRemaining} landmine check{checksRemaining !== 1 ? "s" : ""}
            </span>
          )}
          <span className="text-xs font-bold" style={{ color }}>{score}%</span>
        </div>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function InterrogationPanel({
  data, answeredIds, onAnswer,
}: {
  data: InterrogationResult;
  answeredIds: string[];
  onAnswer: (id: string, field: string, value: string) => void;
}) {
  const [inputVals, setInputVals] = useState<Record<string, string>>({});
  const { critical_questions: questions, kg_insights: insights,
          inferred_conditions: inferred, completeness_score: score,
          delta_message: delta, landmine_checks_remaining: checksRemaining } = data;

  const landmineQs = questions.filter(q => q.landmine_check);
  const regularQs  = questions.filter(q => !q.landmine_check);

  if (questions.length === 0 && insights.length === 0 && inferred.length === 0) return null;

  return (
    <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4 shadow-sm space-y-3 dark:border-blue-800 dark:bg-blue-900/20">
      <CompletenessBar score={score} checksRemaining={checksRemaining} />
      <p className="text-xs text-slate-600 leading-relaxed">{delta}</p>

      {/* ── Landmine symptom checks ─────────────────────────────────────── */}
      {landmineQs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5">
            <MineSvg color="#dc2626" size={12} />
            <p className="text-xs font-bold uppercase tracking-wide text-red-700">
              Landmine Symptom Check
            </p>
          </div>
          {landmineQs.map((q) => {
            const rl = q.risk_level ?? "medium";
            return (
              <div key={q.id}
                className={`rounded-xl border-2 p-3.5 space-y-2.5 ${LM_CHECK_BORDER[rl]}`}>
                {/* Disease header */}
                <div className="flex items-center gap-2 flex-wrap">
                  <MineSvg color={RISK_BORDER[rl]} size={11} />
                  <span className="text-xs font-bold text-slate-800">{q.disease_name}</span>
                  <span className="text-xs text-slate-500">({q.disease_korean})</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${RISK_BADGE[rl]}`}>
                    {rl.toUpperCase()} RISK
                  </span>
                </div>
                {/* The question itself */}
                <p className="text-sm text-slate-800 leading-relaxed font-medium">{q.question}</p>
                {/* Why we're asking */}
                <p className="text-xs text-slate-500 leading-snug italic">{q.context}</p>
                {/* Why it matters */}
                <p className="text-xs rounded bg-white/70 px-2.5 py-1.5 text-slate-600 border border-slate-200">
                  <span className="font-semibold">Why this matters: </span>{q.why_critical}
                </p>
                {/* Yes / No buttons */}
                <div className="flex gap-2 pt-0.5">
                  <button type="button"
                    onClick={() => onAnswer(`${q.id}:yes`, q.field, q.symptom_value ?? "")}
                    className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${LM_CHECK_BTN_YES[rl]}`}>
                    {q.yes_label ?? "Yes, I've noticed this"}
                  </button>
                  <button type="button"
                    onClick={() => onAnswer(`${q.id}:no`, q.field, "")}
                    className="flex-1 rounded-lg bg-white border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 transition-colors">
                    {q.no_label ?? "No, not really"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Inferred conditions */}
      {inferred.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">KG signals</p>
          {inferred.map((c, i) => (
            <div key={i} className={`rounded-lg border px-2.5 py-2 text-xs ${SEV_INSIGHT["medium"]}`}>
              <span className="font-semibold">{c.name}</span>
              <span className="ml-1.5 rounded-full bg-white/60 px-1.5 py-0.5 text-xs">
                {c.confidence}
              </span>
              <p className="mt-0.5 opacity-80">{c.reason}</p>
            </div>
          ))}
        </div>
      )}

      {/* KG insights (risk cascades, avoidance) */}
      {insights.filter(i => i.type === "risk_cascade" || i.type === "avoidance").slice(0, 3).length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">KG insights</p>
          {insights
            .filter(i => i.type === "risk_cascade" || i.type === "avoidance")
            .slice(0, 3)
            .map((ins, i) => (
              <div key={i} className={`rounded border px-2.5 py-1.5 text-xs ${SEV_INSIGHT[ins.severity]}`}>
                {ins.text}
                {ins.evidence_count > 0 && (
                  <span className="ml-1.5 opacity-60">({ins.evidence_count} source{ins.evidence_count !== 1 ? "s" : ""})</span>
                )}
              </div>
            ))}
        </div>
      )}

      {/* Regular assessment questions */}
      {regularQs.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Sharpen your assessment ({regularQs.length} question{regularQs.length !== 1 ? "s" : ""})
          </p>
          {regularQs.map((q) => (
            <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 dark:border-gray-600 dark:bg-gray-700">
              <p className="text-xs font-semibold text-slate-800 dark:text-gray-100">{q.question}</p>
              {q.context && <p className="text-xs text-slate-500 leading-snug dark:text-gray-400">{q.context}</p>}

              {q.type === "confirm" && (
                <div className="flex gap-2">
                  <button type="button"
                    onClick={() => onAnswer(q.id, q.field, q.value!)}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700">
                    Yes, confirmed
                  </button>
                  <button type="button"
                    onClick={() => onAnswer(`denied:${q.value}`, q.field, "")}
                    className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-200">
                    No
                  </button>
                </div>
              )}

              {(q.type === "text" || q.type === "number") && (
                <div className="flex gap-2">
                  <input
                    type={q.type === "number" ? "number" : "text"}
                    placeholder={q.hint ?? ""}
                    value={inputVals[q.id] ?? ""}
                    onChange={e => setInputVals(v => ({ ...v, [q.id]: e.target.value }))}
                    onKeyDown={e => {
                      if (e.key === "Enter" && (inputVals[q.id] ?? "").trim())
                        onAnswer(q.id, q.field, (inputVals[q.id] ?? "").trim());
                    }}
                    className="flex-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs focus:border-blue-400 focus:outline-none"
                  />
                  <button type="button"
                    onClick={() => {
                      const v = (inputVals[q.id] ?? "").trim();
                      if (v) onAnswer(q.id, q.field, v);
                    }}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700">
                    Add
                  </button>
                  <button type="button"
                    onClick={() => onAnswer(q.id, "", "")}
                    className="text-xs text-slate-400 hover:underline">Skip</button>
                </div>
              )}

              {q.type === "select" && q.options && (
                <div className="flex flex-wrap gap-1.5">
                  {q.options.map(opt => (
                    <button key={opt} type="button"
                      onClick={() => onAnswer(q.id, q.field, opt)}
                      className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors">
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Profile editor ───────────────────────────────────────────────────────────
const CHIP_COLORS: Record<string, string> = {
  age:        "bg-blue-100 text-blue-800 border-blue-200",
  gender:     "bg-slate-100 text-slate-700 border-slate-200",
  conditions: "bg-amber-100 text-amber-800 border-amber-200",
  symptoms:   "bg-orange-100 text-orange-800 border-orange-200",
  medications:"bg-purple-100 text-purple-800 border-purple-200",
  goals:      "bg-emerald-100 text-emerald-800 border-emerald-200",
};

function ProfileEditor({
  ctx, onRemove, onClear,
}: {
  ctx: UserContext;
  onRemove: (field: string, value: string) => void;
  onClear: () => void;
}) {
  type Chip = { field: string; value: string; label: string };
  const chips: Chip[] = [];
  if (ctx.age)    chips.push({ field: "age",    value: String(ctx.age),   label: `Age ${ctx.age}` });
  if (ctx.gender) chips.push({ field: "gender", value: ctx.gender,        label: ctx.gender });
  (ctx.conditions  ?? []).forEach(v => chips.push({ field: "conditions",  value: v, label: v }));
  (ctx.symptoms    ?? []).forEach(v => chips.push({ field: "symptoms",    value: v, label: v }));
  (ctx.medications ?? []).forEach(v => chips.push({ field: "medications", value: v, label: v }));
  (ctx.goals       ?? []).forEach(v => chips.push({ field: "goals",       value: v, label: v }));

  if (chips.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {chips.map(({ field, value, label }, i) => (
          <span key={i}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${CHIP_COLORS[field] ?? "bg-slate-100 text-slate-700 border-slate-200"}`}>
            {label}
            <button type="button"
              onClick={() => onRemove(field, value)}
              className="ml-0.5 rounded-full hover:bg-black/10 leading-none w-3.5 h-3.5 flex items-center justify-center text-[10px] font-bold"
              title={`Remove ${label}`}>
              ×
            </button>
          </span>
        ))}
      </div>
      <button type="button" onClick={onClear}
        className="text-xs text-slate-400 hover:text-red-500 transition-colors">
        Clear all profile info
      </button>
    </div>
  );
}

// ─── Pipeline status widget ───────────────────────────────────────────────────
function PipelineWidget() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    fetchPipelineStatus().then(setStatus).catch(() => {});
    const id = setInterval(() => fetchPipelineStatus().then(setStatus).catch(() => {}), 30000);
    return () => clearInterval(id);
  }, []);

  if (!status) return null;
  const isRunning = status.state === "running";
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs flex items-center justify-between gap-2 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${isRunning ? "bg-green-400 animate-pulse" : "bg-slate-300 dark:bg-gray-500"}`} />
        <span className="text-slate-500 dark:text-gray-400">
          {isRunning
            ? "Fetching new evidence…"
            : status.next_run_in_minutes != null
              ? `Next update in ${status.next_run_in_minutes}m`
              : "Scheduler ready"}
        </span>
        {status.last_new_papers != null && !isRunning && (
          <span className="text-slate-400 dark:text-gray-500">· +{status.last_new_papers} papers last run</span>
        )}
      </div>
      <button type="button"
        disabled={isRunning || triggering}
        onClick={async () => {
          setTriggering(true);
          await triggerPipeline().catch(() => {});
          setTimeout(() => { fetchPipelineStatus().then(setStatus).catch(() => {}); setTriggering(false); }, 1000);
        }}
        className="rounded px-2 py-0.5 text-xs bg-white border border-slate-200 text-slate-500 hover:border-blue-300 hover:text-blue-600 disabled:opacity-40 transition-colors dark:bg-gray-700 dark:border-gray-600 dark:text-gray-400 dark:hover:border-blue-500 dark:hover:text-blue-400">
        {isRunning || triggering ? "Running…" : "Run now"}
      </button>
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

  // ── Interrogation agent ──────────────────────────────────────────────────
  const [interrogation, setInterrogation] = useState<InterrogationResult | null>(null);
  const [answeredIds, setAnsweredIds]     = useState<string[]>([]);
  const [interrogating, setInterrogating] = useState(false);

  // ── Landmine detection ───────────────────────────────────────────────────
  const [landmineData, setLandmineData]   = useState<LandmineResult | null>(null);
  const [selectedLandmine, setSelectedLandmine] = useState<LandmineDisease | null>(null);

  // ── Food chain explorer ──────────────────────────────────────────────────
  const [foodInput, setFoodInput]         = useState("");
  const [chainLoading, setChainLoading]   = useState(false);
  const [chainData, setChainData]         = useState<FoodChainResponse | null>(null);

  // ── Trajectory tracking ────────────────────────────────────────────────
  const [trajectory, setTrajectory]       = useState<Snapshot[]>([]);
  const userTokenRef = useRef<string>("");
  const [showBots, setShowBots]           = useState(false);
  const [currentToken, setCurrentToken]   = useState("");

  const autoSubmitted = useRef(false);

  // Generate stable user token from context hash
  useEffect(() => {
    try {
      const stored = localStorage.getItem("health_user_token");
      if (stored) {
        userTokenRef.current = stored;
        setCurrentToken(stored);
      } else {
        const token = "u_" + Math.random().toString(36).slice(2, 14) + Date.now().toString(36);
        localStorage.setItem("health_user_token", token);
        userTokenRef.current = token;
        setCurrentToken(token);
      }
      // Load existing trajectory
      if (userTokenRef.current) {
        fetchTrajectory(userTokenRef.current)
          .then(setTrajectory)
          .catch(() => {});
      }
    } catch { /* SSR or localStorage unavailable */ }
  }, []);

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
      // Async: save snapshot for trajectory tracking
      const ux = ageToX(ctx.age);
      const uy = conditionsToY(ctx.conditions ?? [], ctx.symptoms ?? [], ctx.age);
      const zone = getZoneAt(uy).name;
      if (userTokenRef.current) {
        saveSnapshot(userTokenRef.current, ctx, ux, uy, zone)
          .then(() => fetchTrajectory(userTokenRef.current))
          .then(setTrajectory)
          .catch(() => {});
      }
      // Async: run interrogation agent after map loads
      setInterrogating(true);
      fetchInterrogation(ctx, answeredIds)
        .then(setInterrogation)
        .catch(() => {/* silent — interrogation is enhancement only */})
        .finally(() => setInterrogating(false));
      // Async: landmine detection (non-blocking)
      fetchLandmines(ctx)
        .then((data) => {
          setLandmineData(data);
          // Update snapshot with landmine risk data
          if (userTokenRef.current && data?.landmines) {
            const risks: Record<string, string> = {};
            data.landmines.forEach(l => { risks[l.name] = l.risk_level; });
            saveSnapshot(userTokenRef.current, ctx, ux, uy, zone, risks).catch(() => {});
          }
        })
        .catch(() => {/* silent — landmine detection is enhancement only */});
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(/failed to fetch|network error|load failed/i.test(msg)
        ? "Cannot reach the API server. Is it running?"
        : msg);
    } finally {
      setLoading(false);
    }
  }, [answeredIds]);

  // ── Profile remove / clear — must be after submitContext ──────────────────
  const handleRemoveFromProfile = useCallback((field: string, value: string) => {
    if (!loadedCtx) return;
    let updated: UserContext = { ...loadedCtx };
    if (field === "conditions")       updated = { ...updated, conditions:  (updated.conditions  ?? []).filter(v => v !== value) };
    else if (field === "symptoms")    updated = { ...updated, symptoms:    (updated.symptoms    ?? []).filter(v => v !== value) };
    else if (field === "medications") updated = { ...updated, medications: (updated.medications ?? []).filter(v => v !== value) };
    else if (field === "goals")       updated = { ...updated, goals:       (updated.goals       ?? []).filter(v => v !== value) };
    else if (field === "age")         updated = { ...updated, age: null };
    else if (field === "gender")      updated = { ...updated, gender: null };
    else return;
    setLoadedCtx(updated);
    try { localStorage.setItem("health_context", JSON.stringify(updated)); } catch { /* ignore */ }
    submitContext(updated);
  }, [loadedCtx, submitContext]);

  const handleClearProfile = useCallback(() => {
    setLoadedCtx(null);
    setMapData(null);
    setInterrogation(null);
    setAnsweredIds([]);
    setLandmineData(null);
    setSelectedLandmine(null);
    setSelectedRisk(null);
    try { localStorage.removeItem("health_context"); } catch { /* ignore */ }
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
      const result = await fetchContextFromText(introText);
      const ctx = result.context;
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
      const result = await fetchContextFromText(refineText);
      const merged = mergeContexts(loadedCtx ?? {}, result.context);
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

  // ── Interrogation answer handler ─────────────────────────────────────────
  const handleAnswer = useCallback((id: string, field: string, value: string) => {
    const newAnswered = [...answeredIds, id];
    setAnsweredIds(newAnswered);

    // Landmine symptom check: "yes" adds the symptom and re-renders the map;
    // "no" (id ends with :no) just records the answer — no context change.
    const isLandmineYes = id.startsWith("lm_check:") && id.endsWith(":yes");
    const isLandmineNo  = id.startsWith("lm_check:") && id.endsWith(":no");

    // Apply answer to context if it adds information
    let patch: Partial<UserContext> = {};
    if (isLandmineYes && value) {
      // Confirmed early warning sign → add to symptoms → map position shifts
      patch = { symptoms: [...(loadedCtx?.symptoms ?? []), value].filter((v, i, a) => a.indexOf(v) === i) };
    } else if (!isLandmineNo) {
      if (field === "conditions" && value) {
        patch = { conditions: [...(loadedCtx?.conditions ?? []), value].filter((v, i, a) => a.indexOf(v) === i) };
      } else if (field === "medications" && value && value.toLowerCase() !== "none") {
        patch = { medications: [...(loadedCtx?.medications ?? []), value].filter((v, i, a) => a.indexOf(v) === i) };
      } else if (field === "symptoms" && value) {
        patch = { symptoms: [...(loadedCtx?.symptoms ?? []), value].filter((v, i, a) => a.indexOf(v) === i) };
      } else if (field === "goals" && value) {
        patch = { goals: [...(loadedCtx?.goals ?? []), value].filter((v, i, a) => a.indexOf(v) === i) };
      } else if (field === "way_of_living" && value) {
        patch = { way_of_living: value };
      } else if (field === "age" && value) {
        const n = parseInt(value, 10);
        if (!isNaN(n) && n > 0) patch = { age: n };
      }
    }

    const updated = Object.keys(patch).length > 0 ? { ...loadedCtx, ...patch } : loadedCtx;
    if (updated && Object.keys(patch).length > 0) {
      setLoadedCtx(updated as UserContext);
      try { localStorage.setItem("health_context", JSON.stringify(updated)); } catch { /* ignore */ }
      submitContext(updated as UserContext);
    } else {
      // No context change — refresh interrogation + landmines with new answered list
      if (loadedCtx) {
        setInterrogating(true);
        fetchInterrogation(loadedCtx, newAnswered)
          .then(setInterrogation)
          .catch(() => {})
          .finally(() => setInterrogating(false));
        fetchLandmines(loadedCtx)
          .then(setLandmineData)
          .catch(() => {});
      }
    }
  }, [answeredIds, loadedCtx, submitContext]);

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

  // ── Persona derivation ──────────────────────────────────────────────────
  const personaData = useMemo(
    () => derivePersona(userY, activeConditions, trajectory),
    [userY, activeConditions, trajectory],
  );

  // ── Synthetic bots ──────────────────────────────────────────────────────
  const bots = useMemo(
    () => generateBots(ctx.age, activeConditions, activeSymptoms),
    [ctx.age, activeConditions, activeSymptoms],
  );

  // ── Health ID restore handler ───────────────────────────────────────────
  const handleRestoreToken = useCallback((newToken: string) => {
    try {
      localStorage.setItem("health_user_token", newToken);
    } catch { /* ignore */ }
    userTokenRef.current = newToken;
    setCurrentToken(newToken);
    fetchTrajectory(newToken)
      .then(setTrajectory)
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-gray-950">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur-sm dark:border-gray-700 dark:bg-gray-900/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 flex-wrap gap-2">
          <div>
            <h1 className="text-lg font-bold text-slate-900 dark:text-gray-100">Health Journey Map</h1>
            <p className="text-xs text-slate-500 hidden sm:block dark:text-gray-400">Your personal health landscape — navigate toward your best health</p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <Link href="/" className="text-slate-500 hover:text-slate-800 dark:text-gray-400 dark:hover:text-gray-200">← Home</Link>
            <Link href="/kg" className="text-slate-500 hover:text-slate-800 dark:text-gray-400 dark:hover:text-gray-200">KG Status</Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">

          {/* ── LEFT panel ───────────────────────────────────────────────── */}
          <div className="w-full lg:w-80 lg:flex-shrink-0 space-y-4">

            {/* ── CASE A: Context loaded from home page ──────────────────── */}
            {hasCtx ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4 dark:border-gray-700 dark:bg-gray-800">
                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide dark:text-gray-100">Your Profile</h2>
                    {loading && (
                      <span className="text-xs text-blue-600 animate-pulse dark:text-blue-400">Locating…</span>
                    )}
                    {hasSubmitted && !loading && (
                      <span className="text-xs text-emerald-600 font-medium dark:text-emerald-400">Map ready</span>
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-gray-400">
                    Using info from your home profile.
                  </p>
                </div>

                {/* Editable profile chips */}
                <ProfileEditor
                  ctx={loadedCtx!}
                  onRemove={handleRemoveFromProfile}
                  onClear={handleClearProfile}
                />

                {/* "Add more" toggle */}
                <button
                  type="button"
                  onClick={() => setShowRefine(v => !v)}
                  className="w-full rounded-lg border border-dashed border-slate-300 py-2 text-xs text-slate-500 hover:border-blue-400 hover:text-blue-600 transition-colors dark:border-gray-600 dark:text-gray-400 dark:hover:border-blue-500 dark:hover:text-blue-400"
                >
                  {showRefine ? "▲ Hide" : "▾ Tell me more — medications, goals, lifestyle…"}
                </button>

                {/* Conversational refinement input */}
                {showRefine && (
                  <div className="space-y-2">
                    <p className="text-xs text-slate-600 leading-relaxed dark:text-gray-300">{refinePrompt}</p>
                    <textarea
                      value={refineText}
                      onChange={e => setRefineText(e.target.value)}
                      placeholder="e.g. I also take Metformin and try to walk 30 min a day. My goal is to sleep better."
                      rows={3}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:outline-none resize-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-500"
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
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4 dark:border-gray-700 dark:bg-gray-800">
                <div>
                  <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide dark:text-gray-100">Tell Me About Yourself</h2>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed dark:text-gray-400">
                    Just type naturally — age, health conditions, symptoms, medications, goals. No need for a form.
                  </p>
                </div>
                <textarea
                  value={introText}
                  onChange={e => setIntroText(e.target.value)}
                  placeholder={`e.g. "I'm 48, female, have Type 2 diabetes and high blood pressure. I've been feeling tired lately and want to eat better."`}
                  rows={5}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm placeholder:text-slate-400 focus:border-blue-400 focus:outline-none resize-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-500"
                />
                {introError && <p className="text-xs text-red-600 dark:text-red-400">{introError}</p>}
                <button
                  type="button"
                  onClick={handleIntroSubmit}
                  disabled={introLoading || !introText.trim()}
                  className="w-full rounded-xl bg-blue-600 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {introLoading ? "Finding your position…" : "Show me my health map →"}
                </button>
                <p className="text-xs text-center text-slate-400 dark:text-gray-500">
                  Or go to <Link href="/" className="text-blue-500 hover:underline">Home</Link> for a full guided experience.
                </p>
              </div>
            )}

            {/* ── Zone indicator ─────────────────────────────────────────── */}
            {(hasCtx || hasSubmitted) && (
              <div className="rounded-2xl border-2 bg-white p-4 shadow-sm dark:bg-gray-800"
                style={{ borderColor: zone.hex }}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: zone.hex }} />
                  <span className="text-sm font-bold" style={{ color: zone.hex }}>{zone.name}</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed dark:text-gray-300">
                  <NarrativeText text={narrative} />
                </p>
              </div>
            )}

            {/* ── Health Persona Card ───────────────────────────────────── */}
            {(hasCtx || hasSubmitted) && (
              <HealthPersonaCard
                persona={personaData.persona}
                zone={personaData.zone}
                complexity={personaData.complexity}
                momentum={personaData.momentum}
                score={personaData.score}
                conditionCount={activeConditions.length}
              />
            )}

            {/* ── People Like You (Synthetic Bots) ────────────────────────── */}
            {(hasCtx || hasSubmitted) && bots.length > 0 && (
              <BotPanel
                bots={bots}
                showBots={showBots}
                onToggle={() => setShowBots(v => !v)}
                trajectory={trajectory}
              />
            )}

            {/* ── Health Journey Dashboard ────────────────────────────────── */}
            {(hasCtx || hasSubmitted) && trajectory.length > 0 && (
              <JourneyPanel trajectory={trajectory} currentY={userY} />
            )}

            {/* ── Interrogation agent panel ───────────────────────────────── */}
            {(interrogation || interrogating) && (
              <div>
                {interrogating && !interrogation && (
                  <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4 text-xs text-slate-500 animate-pulse">
                    Analysing your profile…
                  </div>
                )}
                {interrogation && (
                  <InterrogationPanel
                    data={interrogation}
                    answeredIds={answeredIds}
                    onAnswer={handleAnswer}
                  />
                )}
              </div>
            )}

            {/* ── Safest path directions ──────────────────────────────────── */}
            {steps.length > 0 && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-sm dark:border-emerald-800 dark:bg-emerald-900/20">
                <h3 className="text-xs font-bold uppercase tracking-wide text-emerald-700 mb-3 dark:text-emerald-400">
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
                        <p className="text-xs font-semibold text-slate-800 dark:text-gray-100">{step.action}</p>
                        {step.reason && (
                          <p className="text-xs text-slate-500 leading-snug mt-0.5 dark:text-gray-400">{step.reason}</p>
                        )}
                        {step.evidence?.length > 0 && (
                          <p className="text-xs text-emerald-600 mt-0.5 dark:text-emerald-400">
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
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-600 mb-3 dark:text-gray-400">
                Food → Nutrient → Effect
              </h3>
              <form onSubmit={handleFoodChain} className="flex gap-2 mb-3">
                <input type="text" value={foodInput} onChange={e => setFoodInput(e.target.value)}
                  placeholder="e.g. Salmon, Spinach"
                  className="flex-1 min-w-0 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm focus:border-violet-400 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-500" />
                <button type="submit" disabled={chainLoading || !foodInput.trim()}
                  className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50 flex-shrink-0">
                  {chainLoading ? "…" : "Trace"}
                </button>
              </form>
              {chainData && <ChainPanel chain={chainData} />}
            </div>

            {/* ── Selected risk info ──────────────────────────────────────── */}
            {selectedRisk && (
              <InfoPanel risk={selectedRisk} onClose={() => setSelectedRisk(null)} />
            )}

            {/* ── Selected landmine panel ─────────────────────────────────── */}
            {selectedLandmine && (
              <LandminePanel landmine={selectedLandmine} onClose={() => setSelectedLandmine(null)} />
            )}

            {/* ── Pipeline status widget ──────────────────────────────────── */}
            <PipelineWidget />

            {/* ── Health ID Badge ──────────────────────────────────────────── */}
            <HealthIdBadge token={currentToken} onRestore={handleRestoreToken} />
          </div>

          {/* ── RIGHT: Map ───────────────────────────────────────────────── */}
          <div className="flex-1 min-w-0 space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 bg-slate-50 flex-wrap gap-1.5 dark:border-gray-700 dark:bg-gray-700">
                <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap dark:text-gray-400">
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-green-500" /> Thriving</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Navigation</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-orange-400" /> Risk</span>
                  <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Critical</span>
                </div>
                <span className="text-xs text-slate-400 dark:text-gray-500">
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

                {/* Landmine markers — rendered below user marker */}
                {landmineData?.landmines.map((lm) => (
                  <LandmineMarker
                    key={lm.name}
                    x={lm.map_x} y={lm.map_y}
                    riskLevel={lm.risk_level}
                    name={lm.name}
                    korean={lm.korean}
                    selected={selectedLandmine?.name === lm.name}
                    onClick={() => setSelectedLandmine(
                      selectedLandmine?.name === lm.name ? null : lm
                    )}
                  />
                ))}

                {risks.map((risk, i) => {
                  const { x, y } = riskXY(i, userX, userY);
                  return (
                    <RiskPin key={risk.name + i} x={x} y={y} sev={riskSev(risk)} label={risk.name}
                      selected={selectedRisk?.name === risk.name}
                      onClick={() => setSelectedRisk(selectedRisk?.name === risk.name ? null : risk)} />
                  );
                })}

                {/* Trajectory: animated gradient path with zone-transition diamonds */}
                {trajectory.length > 1 && <TrajectoryPath snapshots={trajectory} />}

                {/* Synthetic bot ghost markers + trajectory trails */}
                {showBots && bots.map((bot) => {
                  const bp = derivePersona(bot.currentY, bot.conditions, trajectory);
                  return (
                    <g key={bot.id}>
                      <BotTrajectoryTrail points={bot.trajectory} color={bot.color} />
                      <BotGhostMarker
                        x={bot.currentX} y={bot.currentY}
                        color={bot.color} name={bot.name}
                        personaCode={bp.persona.code}
                      />
                    </g>
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
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-3 dark:text-gray-400">
                  Risk Zones Near You ({risks.length})
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {risks.map((risk, i) => {
                    const sev = riskSev(risk);
                    const isSelected = selectedRisk?.name === risk.name;
                    return (
                      <button key={i} type="button"
                        onClick={() => setSelectedRisk(isSelected ? null : risk)}
                        className={`text-left rounded-xl border-l-4 border border-slate-100 p-3 transition-all hover:shadow-md dark:border-gray-700 ${isSelected ? "ring-2 ring-offset-1 dark:ring-offset-gray-800" : ""}`}
                        style={{ borderLeftColor: SEV_HEX[sev], outlineColor: isSelected ? SEV_HEX[sev] : undefined }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-slate-800 truncate pr-2 dark:text-gray-100">{risk.name}</span>
                          <span className="text-xs font-bold rounded px-1.5 py-0.5 flex-shrink-0"
                            style={{ backgroundColor: SEV_GLOW[sev], color: SEV_HEX[sev] }}>
                            {sev.toUpperCase()}
                          </span>
                        </div>
                        {risk.reason && <p className="text-xs text-slate-500 leading-snug line-clamp-2 dark:text-gray-400">{risk.reason}</p>}
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 capitalize dark:bg-gray-700 dark:text-gray-400">{risk.kind}</span>
                          <span className="text-xs text-slate-400 dark:text-gray-500">{risk.evidence?.length ?? 0} source{risk.evidence?.length !== 1 ? "s" : ""}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Landmine grid ─────────────────────────────────────────── */}
            {landmineData && (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
                <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500 mb-3 flex items-center gap-2 dark:text-gray-400">
                  Landmine Diseases — Navigate Around These
                  <span className="rounded-full bg-red-100 text-red-700 px-2 py-0.5 text-xs font-bold normal-case dark:bg-red-900/20 dark:text-red-400">
                    {landmineData.landmines.filter(l => l.risk_level !== "none").length} on your radar
                  </span>
                </h3>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {landmineData.landmines.map((lm) => {
                    const isSelected = selectedLandmine?.name === lm.name;
                    const bc = RISK_BORDER[lm.risk_level] ?? "#94a3b8";
                    return (
                      <button key={lm.name} type="button"
                        onClick={() => setSelectedLandmine(isSelected ? null : lm)}
                        className={`text-left rounded-xl border-l-4 border border-slate-100 p-3 transition-all hover:shadow-md dark:border-gray-700 ${isSelected ? "ring-2 ring-offset-1 dark:ring-offset-gray-800" : ""}`}
                        style={{ borderLeftColor: bc, outlineColor: isSelected ? bc : undefined,
                                 opacity: lm.risk_level === "none" ? 0.5 : 1 }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-slate-800 truncate pr-1 dark:text-gray-100">{lm.name}</span>
                          <span className={`text-xs font-bold rounded px-1.5 py-0.5 flex-shrink-0 ${RISK_BADGE[lm.risk_level]}`}>
                            {lm.risk_level.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-gray-400">{lm.korean}</p>
                        {lm.risk_factors_present.length > 0 && (
                          <p className="text-xs text-red-600 mt-1 dark:text-red-400">
                            {lm.risk_factors_present.length} risk factor{lm.risk_factors_present.length !== 1 ? "s" : ""} present
                          </p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Early signals ─────────────────────────────────────────── */}
            {earlySignals.length > 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm dark:border-amber-800 dark:bg-amber-900/20">
                <h3 className="text-xs font-bold uppercase tracking-wide text-amber-700 mb-3 dark:text-amber-400">
                  Early Signals — Watch These Indicators
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {earlySignals.map((sig, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <span className="text-amber-500">⚑</span>
                      <span className="font-medium text-slate-800 dark:text-gray-100">{sig.symptom}</span>
                      <span className="text-slate-400 dark:text-gray-500">→</span>
                      <span className="text-amber-800 dark:text-amber-400">{sig.disease}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Empty state ───────────────────────────────────────────── */}
            {!hasSubmitted && !loading && (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-5 text-center dark:border-gray-600 dark:bg-gray-800/50">
                <p className="text-sm text-slate-500 dark:text-gray-400">
                  {hasCtx
                    ? "Loading your position from profile…"
                    : <>Fill in your profile on the left, or go to <Link href="/" className="text-blue-600 hover:underline dark:text-blue-400">Home</Link> for the full guided experience.</>
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
