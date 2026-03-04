/**
 * API client for Health Navigation server. Base URL: same origin (rewrite) or env NEXT_PUBLIC_API_URL.
 */
import type {
  UserContext,
  ContextFromTextResult,
  InterrogationResult,
  LandmineResult,
  RecommendationsResponse,
  PositionResponse,
  SafestPathResponse,
  EarlySignalGuidanceResponse,
  GeneralGuidanceResponse,
  DrugSubstitutionResponse,
  BiomarkerResponse,
  MechanismResponse,
  DrugInteractionResponse,
  PipelineRun,
  KgExploreResponse,
} from "./types";

const BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "")
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000");
const API = BASE ? BASE : "/api-backend";

async function post<T>(path: string, body: UserContext): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchRecommendations(ctx: UserContext): Promise<RecommendationsResponse> {
  return post("/api/recommendations/foods", ctx);
}

export async function fetchPosition(ctx: UserContext): Promise<PositionResponse> {
  return post("/api/health-map/position", ctx);
}

export async function fetchSafestPath(ctx: UserContext): Promise<SafestPathResponse> {
  return post("/api/health-map/safest-path", ctx);
}

export async function fetchEarlySignals(ctx: UserContext): Promise<EarlySignalGuidanceResponse> {
  return post("/api/guidance/early-signals", ctx);
}

export async function fetchGeneralGuidance(ctx: UserContext): Promise<GeneralGuidanceResponse> {
  return post("/api/guidance/general", ctx);
}

export async function fetchDrugSubstitution(drugs: string[]): Promise<DrugSubstitutionResponse> {
  const res = await fetch(`${API}/api/recommendations/drug-substitution`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drugs }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Suggest canonical/similar terms for spelling and autocomplete. */
export async function fetchSuggestions(query: string, field: "conditions" | "symptoms" | "medications" | "goals"): Promise<string[]> {
  if (!query.trim()) return [];
  const res = await fetch(
    `${API}/api/suggest?q=${encodeURIComponent(query.trim())}&field=${encodeURIComponent(field)}`
  );
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data.suggestions) ? data.suggestions : [];
}

/** Save context encrypted on the server. Returns one-time restore code. */
export async function saveContext(ctx: UserContext): Promise<{ restore_token: string }> {
  const res = await fetch(`${API}/api/me/context/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ctx),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Restore context by one-time code. Code is invalidated after use. */
export async function restoreContext(restoreToken: string): Promise<UserContext> {
  const res = await fetch(`${API}/api/me/context/restore?restore_token=${encodeURIComponent(restoreToken.trim())}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data as UserContext;
}

/** Extract structured context from free-form self-intro text. */
export async function fetchContextFromText(text: string): Promise<ContextFromTextResult> {
  const res = await fetch(`${API}/api/context/from-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.trim() }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  // Support both old shape ({age, conditions, ...}) and new shape ({context, inferred, follow_up})
  if ("context" in data) return data as ContextFromTextResult;
  return { context: data as UserContext, inferred: [], follow_up: [] };
}

/** Landmine disease risk detection — returns all 6 landmines with risk levels. */
export async function fetchLandmines(ctx: UserContext): Promise<LandmineResult> {
  return post("/api/health-map/landmines", ctx);
}

/** Agentic health map interrogation — completeness score + KG-driven critical questions. */
export async function fetchInterrogation(
  context: UserContext,
  answeredFields: string[] = [],
): Promise<InterrogationResult> {
  const res = await fetch(`${API}/api/health-map/interrogate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context, answered_fields: answeredFields }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Pipeline scheduler status. */
export interface PipelineStatus {
  state: "idle" | "running";
  last_run: string | null;
  next_run: string | null;
  next_run_in_minutes: number | null;
  interval_minutes: number;
  last_new_papers: number | null;
  last_valid_triples: number | null;
  last_elapsed_s: number | null;
  runs_completed: number;
  venv_found: boolean;
}

export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${API}/api/pipeline/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function triggerPipeline(): Promise<{ status: string }> {
  const res = await fetch(`${API}/api/pipeline/trigger`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** KG stats for dashboard (Neo4j + optional pipeline). */
export interface KgStats {
  neo4j: {
    nodes?: number;
    relationships?: number;
    by_label?: Record<string, number>;
    by_relationship_type?: Record<string, number>;
    error?: string;
    error_type?: "connection_refused" | "auth_error";
    debug?: { uri?: string; user?: string };
  };
  pipeline?: {
    triples: number;
    with_source_id: number;
    unique_sources: number;
  };
  trend?: Array<{
    date: string;
    nodes: number;
    relationships: number;
  }>;
}

export async function fetchKgStats(): Promise<KgStats> {
  const res = await fetch(`${API}/api/kg/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Pipeline run history. */
export async function fetchPipelineHistory(limit: number = 5): Promise<PipelineRun[]> {
  const res = await fetch(`${API}/api/pipeline/history?limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : data.runs ?? [];
}

/** Live expansion status for real-time dashboard. */
export interface KgLive {
  active: boolean;
  started_at?: string;
  corpus: {
    raw_papers: number;
    extracted: number;
    backlog: number;
  };
  cycles: Array<{
    cycle: number;
    papers: number;
    nodes_delta: number;
    rels_delta: number;
    total_nodes: number;
    total_rels: number;
    time: string;
  }>;
  processes: Array<{
    pid: number;
    cpu: string;
    mem: string;
    elapsed: string;
    name: string;
  }>;
}

export async function fetchKgLive(): Promise<KgLive> {
  const res = await fetch(`${API}/api/kg/live`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Food-chain multi-hop result: Food → Nutrient → Disease/Symptom */
export interface FoodChainLink {
  nutrient: string;
  relationship_type: string;
  target: string;
  target_type: string;
  evidence: Array<{
    source_id: string;
    context: string;
    journal: string;
    pub_date: string;
    source_type: string;
    evidence_type: string;
  }>;
  contains_evidence: Array<{
    source_id: string;
    context: string;
    source_type: string;
  }>;
}

export interface FoodChainResponse {
  food: string;
  chain: FoodChainLink[];
  error?: string;
}

export async function fetchFoodChain(food: string): Promise<FoodChainResponse> {
  const res = await fetch(`${API}/api/kg/food-chain?food=${encodeURIComponent(food.trim())}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Save a context snapshot after map render. */
export async function saveSnapshot(
  userToken: string,
  context: import("./types").UserContext,
  positionX: number | null,
  positionY: number | null,
  zone: string | null,
  landmineRisks?: Record<string, string>,
): Promise<{ snapshot_id: number }> {
  const res = await fetch(`${API}/api/me/snapshot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_token: userToken,
      context,
      position_x: positionX,
      position_y: positionY,
      zone,
      landmine_risks: landmineRisks ?? {},
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Medical KG layer API functions ──────────────────────────────────────────

/** Clinical biomarkers: given conditions, find relevant biomarkers + foods that improve them. */
export async function fetchBiomarkers(conditions: string[]): Promise<BiomarkerResponse> {
  const res = await fetch(`${API}/api/clinical/biomarkers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conditions }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Mechanism graph: Food -> Mechanism -> Disease with evidence chains. */
export async function fetchMechanisms(disease: string): Promise<MechanismResponse> {
  const res = await fetch(`${API}/api/clinical/mechanisms/${encodeURIComponent(disease.trim())}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Drug interactions: given medications, find food contraindications and complements. */
export async function fetchDrugInteractions(medications: string[]): Promise<DrugInteractionResponse> {
  const res = await fetch(`${API}/api/clinical/drug-interactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ medications }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** KG Graph Explorer: subgraph neighborhood around a named entity. */
export async function fetchKgExplore(
  entity: string,
  hops: 1 | 2 = 1,
  limit: number = 80,
): Promise<KgExploreResponse> {
  const params = new URLSearchParams({ entity, hops: String(hops), limit: String(limit) });
  const res = await fetch(`${API}/api/kg/explore?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Fetch trajectory (ordered snapshots) for a user token. */
export async function fetchTrajectory(
  token: string,
  limit: number = 50,
): Promise<import("./types").Snapshot[]> {
  const res = await fetch(
    `${API}/api/me/trajectory?token=${encodeURIComponent(token.trim())}&limit=${limit}`
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
