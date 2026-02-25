/** One KG evidence record linking a food/nutrient to a landmine disease. */
export interface LandmineKgEvidence {
  food: string;
  food_type: string;
  predicate: string;
  source_id: string;
  context: string;
  journal: string;
  pub_date: string;
}

/** One landmine disease with risk assessment. */
export interface LandmineDisease {
  name: string;
  korean: string;
  risk_level: "none" | "low" | "medium" | "high";
  risk_factors_present: string[];
  risk_factors_missing: string[];
  early_warning_signs: string[];
  escape_routes: string[];
  kg_evidence: LandmineKgEvidence[];
  why_critical: string;
  map_x: number;
  map_y: number;
  territory: string;
}

/** Response from /api/health-map/landmines */
export interface LandmineResult {
  landmines: LandmineDisease[];
}

/** Agentic health map interrogation response. */
export interface InterrogationResult {
  completeness_score: number;          // 0-100
  missing_fields: string[];
  kg_insights: Array<{
    type: "risk_cascade" | "protective_food" | "avoidance" | "early_signal";
    text: string;
    entity: string;
    evidence_count: number;
    severity: "high" | "medium" | "low";
  }>;
  inferred_conditions: Array<{
    name: string;
    confidence: string;
    reason: string;
  }>;
  critical_questions: Array<{
    id: string;
    field: string;
    priority: number;
    question: string;
    context: string;
    type: "confirm" | "number" | "text" | "select" | "landmine_symptom";
    value?: string;
    hint?: string;
    options?: string[];
    confidence?: string;
    // Landmine symptom check fields
    landmine_check?: boolean;
    disease_name?: string;
    disease_korean?: string;
    risk_level?: string;
    why_critical?: string;
    yes_label?: string;
    no_label?: string;
    symptom_value?: string;
  }>;
  delta_message: string;
  landmine_checks_remaining?: number;
}

/** A follow-up question to confirm an inferred value or fill a missing field. */
export interface FollowUpQuestion {
  field: string;        // "age" | "conditions" | "gender" | "goals"
  question: string;     // Human-readable question
  type: "confirm" | "number" | "text" | "select";
  value?: string;       // For "confirm": the inferred value being confirmed
  hint?: string;        // Placeholder hint for input types
  options?: string[];   // For "select" type
}

/** Response from /api/context/from-text */
export interface ContextFromTextResult {
  context: UserContext;
  inferred: string[];            // field names that were guessed, not exact-matched
  follow_up: FollowUpQuestion[]; // targeted questions to confirm/fill
}

/** User context (API request body). All fields optional; standardized names. */
export interface UserContext {
  age?: number | null;
  gender?: string | null;
  ethnicity?: string | null;
  location?: string | null;
  way_of_living?: string | null;
  culture?: string | null;
  conditions?: string[];
  symptoms?: string[];
  medications?: string[];
  goals?: string[];
  timezone?: string | null;
  season?: string | null;
}

export interface Evidence {
  source_id: string;
  source_type: string;
  context: string;
  journal: string;
  pub_date: string;
}

export interface FoodRecommendation {
  food: string;
  reason: string;
  evidence: Evidence[];
}

export interface FoodRestriction {
  food: string;
  reason: string;
  evidence: Evidence[];
}

export interface RecommendationsResponse {
  recommended: FoodRecommendation[];
  restricted: FoodRestriction[];
}

export interface NearbyRisk {
  name: string;
  kind: string;
  reason: string;
  evidence: Evidence[];
}

export interface PositionResponse {
  active_conditions: string[];
  active_symptoms: string[];
  nearby_risks: NearbyRisk[];
}

export interface PathStep {
  action: string;
  reason: string;
  evidence: Evidence[];
}

export interface SafestPathResponse {
  steps: PathStep[];
}

export interface EarlySignalItem {
  symptom: string;
  disease: string;
  evidence: Evidence[];
}

export interface EarlySignalGuidanceResponse {
  early_signals: EarlySignalItem[];
  foods_that_reduce: FoodRecommendation[];
  foods_to_avoid: FoodRestriction[];
}

export interface AgeRelatedChangeItem {
  change: string;
  life_stage: string;
  why_pay_attention: string;
  evidence: Evidence[];
}

export interface GeneralGuidanceResponse {
  food_guidance_summary: string;
  age_related_changes: AgeRelatedChangeItem[];
}

/** One food/ingredient that substitutes or complements a drug. */
export interface DrugSubstituteItem {
  food_or_ingredient: string;
  relation: "SUBSTITUTES_FOR" | "COMPLEMENTS_DRUG";
  reason: string;
  evidence: Evidence[];
}

/** Per-drug result: substitutes and complements with evidence. */
export interface DrugSubstitutionItem {
  drug: string;
  substitutes: DrugSubstituteItem[];
  complements: DrugSubstituteItem[];
}

export interface DrugSubstitutionResponse {
  by_drug: DrugSubstitutionItem[];
  disclaimer: string;
}

/** Longitudinal tracking: a single position snapshot. */
export interface Snapshot {
  recorded_at: string;
  age: number | null;
  conditions: string[];
  symptoms: string[];
  position_x: number | null;
  position_y: number | null;
  zone: string | null;
  landmine_risks: Record<string, string>;
}

/** Trajectory: ordered list of snapshots for a user token. */
export interface Trajectory {
  snapshots: Snapshot[];
}

// ── Medical KG layer types ──────────────────────────────────────────────────

export interface BiomarkerEvidence {
  source_id: string;
  context: string;
  journal: string;
  pub_date: string;
}

export interface BiomarkerFoodRec {
  food: string;
  direction: "increases" | "decreases";
  context: string;
  evidence: BiomarkerEvidence;
}

export interface BiomarkerItem {
  biomarker: string;
  disease: string;
  evidence: BiomarkerEvidence;
  food_recommendations: BiomarkerFoodRec[];
}

export interface BiomarkerResponse {
  biomarkers: BiomarkerItem[];
  disclaimer: string;
}

export interface MechanismEvidence {
  source_id: string;
  source_type: string;
  journal: string;
  pub_date: string;
}

export interface MechanismHop {
  context: string;
  evidence: MechanismEvidence;
}

export interface MechanismChain {
  food: string;
  food_type: string;
  mechanism: string;
  mechanism_relationship: string;
  disease: string;
  food_to_mechanism: MechanismHop;
  mechanism_to_disease: MechanismHop;
}

export interface MechanismResponse {
  disease: string;
  mechanism_chains: MechanismChain[];
  disclaimer: string;
}

export interface DrugInteractionEvidence {
  source_id: string;
  source_type: string;
  journal: string;
  pub_date: string;
}

export interface DrugInteractionItem {
  nutrient: string;
  nutrient_type: string;
  context: string;
  evidence: DrugInteractionEvidence;
}

export interface DrugInteractionByDrug {
  drug: string;
  contraindications: DrugInteractionItem[];
  complements: DrugInteractionItem[];
}

export interface DrugInteractionResponse {
  interactions: DrugInteractionByDrug[];
  disclaimer: string;
}
