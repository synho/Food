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
}

export async function fetchKgStats(): Promise<KgStats> {
  const res = await fetch(`${API}/api/kg/stats`);
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
