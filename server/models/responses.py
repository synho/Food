"""
API response models. Standardized field names; zero-error: every recommendation/restriction has evidence[].
"""
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Single evidence record (source_id required)."""
    source_id: str = Field(..., description="e.g. PMC id or FDA/drug label identifier")
    source_type: str = Field(default="PMC", description="PMC | FDA | drug_label for trust differentiation")
    context: str = Field(default="", description="Short quote or description")
    journal: str = Field(default="", description="Journal name if from literature")
    pub_date: str = Field(default="", description="Publication date")


class FoodRecommendation(BaseModel):
    """One recommended food with reason and evidence (at least one)."""
    food: str = Field(..., description="Canonical food name")
    reason: str = Field(..., description="Why recommended")
    evidence: list[Evidence] = Field(..., min_length=1, description="At least one evidence record")


class FoodRestriction(BaseModel):
    """One restricted / not-recommended food with reason and evidence (at least one)."""
    food: str = Field(..., description="Canonical food name")
    reason: str = Field(..., description="Why restricted")
    evidence: list[Evidence] = Field(..., min_length=1, description="At least one evidence record")


class RecommendationsResponse(BaseModel):
    """Food recommendations and restrictions with evidence (zero-error)."""
    recommended: list[FoodRecommendation] = Field(default_factory=list)
    restricted: list[FoodRestriction] = Field(default_factory=list)


class NearbyRisk(BaseModel):
    """A nearby risk (disease or early signal) with evidence."""
    name: str = Field(..., description="Canonical disease or symptom name")
    kind: str = Field(..., description="disease | early_signal")
    reason: str = Field(default="", description="Why this is a risk for the user")
    evidence: list[Evidence] = Field(default_factory=list)


class PositionResponse(BaseModel):
    """User position on the health map and nearby risks (zero-error: risks with evidence when available)."""
    active_conditions: list[str] = Field(default_factory=list, description="User's current conditions (canonical names)")
    active_symptoms: list[str] = Field(default_factory=list, description="User's current symptoms (canonical names)")
    nearby_risks: list[NearbyRisk] = Field(default_factory=list, description="Diseases and early signals to be aware of")


class PathStep(BaseModel):
    """One actionable step for evacuation to safety (with evidence)."""
    action: str = Field(..., description="e.g. Increase X; reduce Y")
    reason: str = Field(..., description="Why this step")
    evidence: list[Evidence] = Field(..., min_length=1)


class SafestPathResponse(BaseModel):
    """Actionable steps to evacuate to safety (zero-error)."""
    steps: list[PathStep] = Field(default_factory=list)


class EarlySignalItem(BaseModel):
    """Symptom as early signal of a disease (with evidence)."""
    symptom: str = Field(..., description="Canonical symptom name")
    disease: str = Field(..., description="Canonical disease name")
    evidence: list[Evidence] = Field(default_factory=list)


class EarlySignalGuidanceResponse(BaseModel):
    """Early signals to watch; foods that reduce vs avoid (zero-error: each item with evidence)."""
    early_signals: list[EarlySignalItem] = Field(default_factory=list)
    foods_that_reduce: list[FoodRecommendation] = Field(default_factory=list)
    foods_to_avoid: list[FoodRestriction] = Field(default_factory=list)


class AgeRelatedChangeItem(BaseModel):
    """One age-related change with why pay attention (evidence)."""
    change: str = Field(..., description="Canonical name of change (e.g. Sarcopenia)")
    life_stage: str = Field(default="", description="When it typically appears (e.g. 30s, 50s)")
    why_pay_attention: str = Field(..., description="Why diet/exercise matter for this change")
    evidence: list[Evidence] = Field(default_factory=list)


class GeneralGuidanceResponse(BaseModel):
    """General guidance: food summary + aging/biology by life stage (zero-error where evidence exists)."""
    food_guidance_summary: str = Field(default="", description="High-level food guidance (e.g. Mediterranean-style, limit sodium)")
    age_related_changes: list[AgeRelatedChangeItem] = Field(default_factory=list)


class DrugSubstituteItem(BaseModel):
    """One food/ingredient that substitutes or complements a drug (with evidence)."""
    food_or_ingredient: str = Field(..., description="Canonical name")
    relation: str = Field(..., description="SUBSTITUTES_FOR | COMPLEMENTS_DRUG")
    reason: str = Field(default="", description="Short why")
    evidence: list[Evidence] = Field(..., min_length=1)


class DrugSubstitutionItem(BaseModel):
    """Per-drug: substitutes and complements with evidence."""
    drug: str = Field(..., description="Canonical drug name")
    substitutes: list[DrugSubstituteItem] = Field(default_factory=list)
    complements: list[DrugSubstituteItem] = Field(default_factory=list)


class DrugSubstitutionResponse(BaseModel):
    """Drug-substituting/complementing foods; evidence from FDA, drug_label, PMC. Not medical advice."""
    by_drug: list[DrugSubstitutionItem] = Field(default_factory=list)
    disclaimer: str = Field(
        default="This is not medical advice. Consult your doctor or pharmacist before changing medication or diet."
    )
