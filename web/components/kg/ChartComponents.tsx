"use client";

// ─── Color palettes ────────────────────────────────────────────────────────────
export const ENTITY_HEX: Record<string, string> = {
  Food:                "#22c55e",
  Disease:             "#ef4444",
  Nutrient:            "#3b82f6",
  Symptom:             "#f97316",
  Drug:                "#a855f7",
  BodySystem:          "#06b6d4",
  LifestyleFactor:     "#eab308",
  AgeRelatedChange:    "#6366f1",
  LifeStage:           "#ec4899",
  Study:               "#94a3b8",
  // Medical entity types
  Biomarker:           "#14b8a6",
  Mechanism:           "#f43f5e",
  ClinicalTrial:       "#8b5cf6",
  BiochemicalPathway:  "#0891b2",
  PopulationGroup:     "#d946ef",
};

export const ENTITY_TWBG: Record<string, string> = {
  Food:                "bg-green-500",
  Disease:             "bg-red-500",
  Nutrient:            "bg-blue-500",
  Symptom:             "bg-orange-500",
  Drug:                "bg-purple-500",
  BodySystem:          "bg-cyan-500",
  LifestyleFactor:     "bg-yellow-500",
  AgeRelatedChange:    "bg-indigo-500",
  LifeStage:           "bg-pink-500",
  Study:               "bg-slate-400",
  Biomarker:           "bg-teal-500",
  Mechanism:           "bg-rose-500",
  ClinicalTrial:       "bg-violet-500",
  BiochemicalPathway:  "bg-cyan-600",
  PopulationGroup:     "bg-fuchsia-500",
};

export const ENTITY_DESC: Record<string, string> = {
  Food:                "Foods & dietary items",
  Disease:             "Medical conditions & disorders",
  Nutrient:            "Vitamins, minerals & compounds",
  Symptom:             "Clinical signs & symptoms",
  Drug:                "Medications & treatments",
  BodySystem:          "Organ systems & physiological domains",
  LifestyleFactor:     "Exercise, sleep, stress & habits",
  AgeRelatedChange:    "Normative age-related changes",
  LifeStage:           "Life phases & age bands",
  Study:               "Published studies (schema reserved)",
  Biomarker:           "Clinical biomarkers & lab values",
  Mechanism:           "Biological mechanisms & pathways",
  ClinicalTrial:       "Registered clinical trials",
  BiochemicalPathway:  "Biochemical & metabolic pathways",
  PopulationGroup:     "Demographic & population groups",
};

export type RelGroup = "beneficial" | "harmful" | "structural" | "relational" | "medical";

export function relGroup(rel: string): RelGroup {
  if (["PREVENTS", "REDUCES_RISK_OF", "ALLEVIATES", "TREATS"].includes(rel)) return "beneficial";
  if (["CAUSES", "AGGRAVATES", "INCREASES_RISK_OF", "CONTRAINDICATED_WITH"].includes(rel)) return "harmful";
  if (["CONTAINS", "PART_OF", "OCCURS_AT"].includes(rel)) return "structural";
  if (["BIOMARKER_FOR", "INCREASES_BIOMARKER", "DECREASES_BIOMARKER", "TARGETS_MECHANISM", "STUDIED_IN"].includes(rel)) return "medical";
  return "relational";
}

export const GROUP_HEX: Record<RelGroup, string> = {
  beneficial: "#22c55e",
  harmful:    "#ef4444",
  structural: "#3b82f6",
  relational: "#a855f7",
  medical:    "#14b8a6",
};

export const GROUP_LABEL: Record<RelGroup, string> = {
  beneficial: "Beneficial",
  harmful:    "Harmful",
  structural: "Structural",
  relational: "Relational",
  medical:    "Medical",
};

export const REL_DESC: Record<string, string> = {
  PREVENTS:             "Reduces risk of disease onset",
  CAUSES:               "Increases risk or directly causes",
  TREATS:               "Used in treatment or management",
  CONTAINS:             "Food → Nutrient link",
  AGGRAVATES:           "Worsens a condition or symptom",
  REDUCES_RISK_OF:      "Lowers risk of disease",
  ALLEVIATES:           "Reduces symptom severity",
  EARLY_SIGNAL_OF:      "Early indicator of disease",
  SUBSTITUTES_FOR:      "Can partly replace a drug",
  COMPLEMENTS_DRUG:     "Works together with a drug",
  AFFECTS:              "General effect (direction unspecified)",
  PART_OF:              "Part of an organ system",
  OCCURS_AT:            "Occurs at this life stage",
  INCREASES_RISK_OF:    "Raises disease risk",
  MODIFIABLE_BY:        "Can be slowed/reversed by diet or exercise",
  EXPLAINS_WHY:         "Explains a health mechanism",
  RELATES_TO:           "General relationship (unclassified)",
  BIOMARKER_FOR:        "Biomarker associated with a disease",
  INCREASES_BIOMARKER:  "Increases a biomarker level",
  DECREASES_BIOMARKER:  "Decreases a biomarker level",
  TARGETS_MECHANISM:    "Targets a biological mechanism",
  STUDIED_IN:           "Studied in a clinical trial",
  CONTRAINDICATED_WITH: "Should not be used together",
};

// ─── SVG Donut chart ───────────────────────────────────────────────────────────
export function DonutChart({ data }: { data: [string, number][] }) {
  const total = data.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return null;

  const R = 38;
  const CX = 55;
  const CY = 55;
  const C = 2 * Math.PI * R;

  let cumDeg = -90;
  const segments = data.map(([label, value]) => {
    const frac = value / total;
    const startDeg = cumDeg;
    cumDeg += frac * 360;
    return { label, value, frac, startDeg };
  });

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 110 110" className="w-36 h-36">
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
      <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
        {segments.map(({ label, value }) => (
          <div key={label} className="flex items-center gap-1 text-xs text-slate-600 dark:text-gray-300">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: ENTITY_HEX[label] ?? "#94a3b8" }}
            />
            <span>{label}</span>
            <span className="text-slate-400 tabular-nums dark:text-gray-500">({value})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Ring score (zero-error compliance) ───────────────────────────────────────
export function RingScore({ value, total }: { value: number; total: number }) {
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
      <p className="mt-1 text-center text-xs font-medium text-slate-700 dark:text-gray-300">Source ID Coverage</p>
      <p className="text-center text-xs text-slate-400 dark:text-gray-500">
        {value.toLocaleString()} / {total.toLocaleString()} triples
      </p>
    </div>
  );
}

// ─── Entity bar chart (colored per type, with descriptions) ───────────────────
export function EntityBarChart({ data }: { data: Record<string, number> }) {
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
                <span className="text-sm font-semibold text-slate-800 dark:text-gray-100">{label}</span>
              </div>
              <span className="text-sm tabular-nums font-medium text-slate-600 dark:text-gray-300">
                {value.toLocaleString()}
              </span>
            </div>
            <div className="h-5 rounded-md bg-slate-100 overflow-hidden dark:bg-gray-700">
              <div
                className={`h-full rounded-md ${bg} transition-all duration-700`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <p className="mt-0.5 text-xs text-slate-400 dark:text-gray-500">{desc}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── Relationship bar chart (semantic colors, with descriptions) ──────────────
export function RelBarChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-3">
        {(["beneficial", "harmful", "structural", "medical", "relational"] as RelGroup[]).map((g) => (
          <div key={g} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-gray-300">
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
                  <span className="text-sm font-semibold text-slate-800 dark:text-gray-100">{label}</span>
                </div>
                <span className="text-sm tabular-nums font-medium text-slate-600 dark:text-gray-300">
                  {value.toLocaleString()}
                </span>
              </div>
              <div className="h-5 rounded-md bg-slate-100 overflow-hidden dark:bg-gray-700">
                <div
                  className="h-full rounded-md transition-all duration-700"
                  style={{ width: `${pct}%`, backgroundColor: hex }}
                />
              </div>
              <p className="mt-0.5 text-xs text-slate-400 dark:text-gray-500">{desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Stat card ────────────────────────────────────────────────────────────────
export function StatCard({
  title, value, sub, accent = "blue", delta,
}: {
  title: string; value: string | number; sub?: string; accent?: "blue" | "emerald" | "violet" | "teal"; delta?: string | null;
}) {
  const border =
    accent === "blue" ? "border-blue-200 dark:border-blue-900" :
    accent === "emerald" ? "border-emerald-200 dark:border-emerald-900" :
    accent === "teal" ? "border-teal-200 dark:border-teal-900" :
    "border-violet-200 dark:border-violet-900";
  const bg =
    accent === "blue" ? "bg-blue-50 dark:bg-blue-900/20" :
    accent === "emerald" ? "bg-emerald-50 dark:bg-emerald-900/20" :
    accent === "teal" ? "bg-teal-50 dark:bg-teal-900/20" :
    "bg-violet-50 dark:bg-violet-900/20";
  const isPositive = delta != null && delta.startsWith("+");
  return (
    <div className={`rounded-xl border-2 ${border} ${bg} p-4 shadow-sm`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{title}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums text-gray-900 dark:text-gray-100">{value}</span>
        {delta != null && (
          <span className={`text-sm font-semibold tabular-nums ${
            isPositive ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"
          }`}>
            {delta}
          </span>
        )}
      </div>
      {sub != null && <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{sub}</div>}
    </div>
  );
}
