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
