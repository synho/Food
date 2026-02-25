"""
Ontology for the Health Navigation KG (aligned with docs/KG_SCHEMA_AND_EVIDENCE.md).
Used to drive extraction prompts and to normalize labels when ingesting into Neo4j.
"""

# Canonical node labels in Neo4j (no spaces; PascalCase)
ENTITY_TYPES = [
    "Disease",
    "Symptom",
    "Food",
    "Nutrient",
    "Drug",
    "LifestyleFactor",
    # Aging/biology (optional in first pass)
    "BodySystem",
    "AgeRelatedChange",
    "LifeStage",
    # Evidence graph (schema reserved; Study nodes not yet ingested from pipeline)
    "Study",
]

# Human-readable names that map to entity types (for extraction prompt and normalization)
ENTITY_TYPE_ALIASES = {
    "disease": "Disease",
    "symptom": "Symptom",
    "food": "Food",
    "nutrient": "Nutrient",
    "drug": "Drug",
    "drug/treatment": "Drug",
    "treatment": "Drug",
    "lifestyle factor": "LifestyleFactor",
    "lifestyle_factor": "LifestyleFactor",
    "lifestylefactor": "LifestyleFactor",
    "body system": "BodySystem",
    "body_system": "BodySystem",
    "bodysystem": "BodySystem",
    "age related change": "AgeRelatedChange",
    "age_related_change": "AgeRelatedChange",
    "life stage": "LifeStage",
    "life_stage": "LifeStage",
    "lifestage": "LifeStage",
}

# Allowed relationship types (predicates) for core + drug substitution
PREDICATES = [
    "PREVENTS",
    "CAUSES",
    "TREATS",
    "CONTAINS",
    "AGGRAVATES",
    "REDUCES_RISK_OF",
    "ALLEVIATES",
    "EARLY_SIGNAL_OF",
    "SUBSTITUTES_FOR",
    "COMPLEMENTS_DRUG",
    "AFFECTS",  # Food/Nutrient affects a Disease/Symptom (direction or magnitude unspecified)
]

# Aging/biology predicates (optional in first pass)
PREDICATES_AGING = [
    "PART_OF",
    "OCCURS_AT",
    "INCREASES_RISK_OF",
    "MODIFIABLE_BY",
    "EXPLAINS_WHY",
]

ALL_PREDICATES = PREDICATES + PREDICATES_AGING

# Canonical entity names for normalization (variant -> canonical).
# SYNC: keep in sync with server/canonical.py CANONICAL_ENTITY_NAMES.
CANONICAL_ENTITY_NAMES = {
    "vitamin d": "Vitamin D",
    "vitamin d3": "Vitamin D",
    "vitamin c": "Vitamin C",
    "omega-3": "Omega-3",
    "omega 3": "Omega-3",
    "type 2 diabetes": "Type 2 diabetes",
    "t2dm": "Type 2 diabetes",
    "type 2 diabetes mellitus": "Type 2 diabetes",
    "prediabetes": "Prediabetes",
    "pre diabetes": "Prediabetes",
    "pre-diabetes": "Prediabetes",
    "pre diabetic": "Prediabetes",
    "pre diabetics": "Prediabetes",
    "hypertension": "Hypertension",
    "high blood pressure": "Hypertension",
    "cardiovascular disease": "Cardiovascular disease",
    "cvds": "Cardiovascular disease",
    "mediterranean diet": "Mediterranean diet",
    "sarcopenia": "Sarcopenia",
    "osteoporosis": "Osteoporosis",
    "metformin": "Metformin",
    "mounjaro": "Mounjaro",
    "maunzaro": "Mounjaro",
    "tirzepatide": "Mounjaro",
    "aspirin": "Aspirin",
    "longevity": "longevity",
    "weight_management": "weight_management",
    "weight management": "weight_management",
    "hypertension_management": "hypertension_management",
    # Landmine diseases — canonical name variants
    "alzheimer": "Alzheimer's disease",
    "alzheimer's": "Alzheimer's disease",
    "alzheimers": "Alzheimer's disease",
    "alzheimer's disease": "Alzheimer's disease",
    "dementia": "Dementia",
    "stroke": "Stroke",
    "cerebral infarction": "Stroke",
    "brain stroke": "Stroke",
    "cerebrovascular accident": "Stroke",
    "cva": "Stroke",
    "pancreatic cancer": "Pancreatic cancer",
    "cancer of the pancreas": "Pancreatic cancer",
    "pancreas cancer": "Pancreatic cancer",
    "chronic kidney disease": "Chronic kidney disease",
    "ckd": "Chronic kidney disease",
    "kidney failure": "Chronic kidney disease",
    "renal failure": "Chronic kidney disease",
    "chronic renal disease": "Chronic kidney disease",
    "depression": "Major depressive disorder",
    "major depression": "Major depressive disorder",
    "clinical depression": "Major depressive disorder",
    "mdd": "Major depressive disorder",
    "major depressive disorder": "Major depressive disorder",
    "heart attack": "Cardiovascular disease",
    "myocardial infarction": "Cardiovascular disease",
    "mi": "Cardiovascular disease",
    "heart disease": "Cardiovascular disease",
    # ── Common Foods ──────────────────────────────────────────────────────
    "salmon": "Salmon",
    "olive oil": "Olive oil",
    "extra virgin olive oil": "Olive oil",
    "evoo": "Olive oil",
    "blueberries": "Blueberries",
    "blueberry": "Blueberries",
    "spinach": "Spinach",
    "broccoli": "Broccoli",
    "almonds": "Almonds",
    "almond": "Almonds",
    "walnuts": "Walnuts",
    "walnut": "Walnuts",
    "avocado": "Avocado",
    "green tea": "Green tea",
    "turmeric": "Turmeric",
    "garlic": "Garlic",
    "ginger": "Ginger",
    "sweet potato": "Sweet potato",
    "sweet potatoes": "Sweet potato",
    "brown rice": "Brown rice",
    "quinoa": "Quinoa",
    "oats": "Oats",
    "oatmeal": "Oats",
    "yogurt": "Yogurt",
    "yoghurt": "Yogurt",
    "kefir": "Kefir",
    "lentils": "Lentils",
    "lentil": "Lentils",
    "tomatoes": "Tomatoes",
    "tomato": "Tomatoes",
    "nuts": "Nuts",
    "seeds": "Seeds",
    "flaxseed": "Flaxseed",
    "flax seed": "Flaxseed",
    "flaxseeds": "Flaxseed",
    "chia seeds": "Chia seeds",
    "chia seed": "Chia seeds",
    "dark chocolate": "Dark chocolate",
    "citrus fruits": "Citrus fruits",
    "citrus fruit": "Citrus fruits",
    # ── Nutrients ─────────────────────────────────────────────────────────
    "vitamin a": "Vitamin A",
    "vitamin e": "Vitamin E",
    "vitamin k": "Vitamin K",
    "vitamin b6": "Vitamin B6",
    "vitamin b12": "Vitamin B12",
    "b12": "Vitamin B12",
    "cobalamin": "Vitamin B12",
    "folate": "Folate",
    "folic acid": "Folate",
    "iron": "Iron",
    "calcium": "Calcium",
    "magnesium": "Magnesium",
    "potassium": "Potassium",
    "zinc": "Zinc",
    "selenium": "Selenium",
    "dietary fiber": "Dietary fiber",
    "fiber": "Dietary fiber",
    "fibre": "Dietary fiber",
    "dietary fibre": "Dietary fiber",
    "protein": "Protein",
    "omega-6": "Omega-6",
    "omega 6": "Omega-6",
    "probiotics": "Probiotics",
    "probiotic": "Probiotics",
    "prebiotics": "Prebiotics",
    "prebiotic": "Prebiotics",
    "antioxidants": "Antioxidants",
    "antioxidant": "Antioxidants",
    "polyphenols": "Polyphenols",
    "polyphenol": "Polyphenols",
    "flavonoids": "Flavonoids",
    "flavonoid": "Flavonoids",
    "lycopene": "Lycopene",
    "curcumin": "Curcumin",
    "resveratrol": "Resveratrol",
    "lutein": "Lutein",
    "melatonin": "Melatonin",
    "tryptophan": "Tryptophan",
    "coenzyme q10": "Coenzyme Q10",
    "coq10": "Coenzyme Q10",
    # ── Dietary Patterns ──────────────────────────────────────────────────
    "dash diet": "DASH diet",
    "plant-based diet": "Plant-based diet",
    "plant based diet": "Plant-based diet",
    "vegan diet": "Vegan diet",
    "vegan": "Vegan diet",
    "vegetarian diet": "Vegetarian diet",
    "vegetarian": "Vegetarian diet",
    "ketogenic diet": "Ketogenic diet",
    "keto diet": "Ketogenic diet",
    "keto": "Ketogenic diet",
    "whole food diet": "Whole food diet",
    "anti-inflammatory diet": "Anti-inflammatory diet",
    "anti inflammatory diet": "Anti-inflammatory diet",
    # ── General Health Conditions ─────────────────────────────────────────
    "obesity": "Obesity",
    "iron-deficiency anaemia": "Iron-deficiency anaemia",
    "iron deficiency anaemia": "Iron-deficiency anaemia",
    "iron deficiency anemia": "Iron-deficiency anaemia",
    "iron-deficiency anemia": "Iron-deficiency anaemia",
    "insomnia": "Insomnia",
    "constipation": "Constipation",
    "irritable bowel syndrome": "Irritable bowel syndrome",
    "ibs": "Irritable bowel syndrome",
    "gastroesophageal reflux disease": "Gastroesophageal reflux disease",
    "gerd": "Gastroesophageal reflux disease",
    "acid reflux": "Gastroesophageal reflux disease",
    "non-alcoholic fatty liver disease": "Non-alcoholic fatty liver disease",
    "nafld": "Non-alcoholic fatty liver disease",
    "fatty liver": "Non-alcoholic fatty liver disease",
    "chronic inflammation": "Chronic inflammation",
    "oxidative stress": "Oxidative stress",
}


def normalize_entity_name(name: str, _entity_type: str = "") -> str:
    """Map entity name to canonical form when possible (e.g. Vitamin D, Type 2 diabetes)."""
    if not name or not isinstance(name, str):
        return name or ""
    key = name.strip().lower()
    return CANONICAL_ENTITY_NAMES.get(key) or name.strip()


def normalize_entity_name_for_merge(name: str) -> str:
    """Return lowercased name for MERGE key to prevent case-sensitive duplicates.
    Always lowercases; the display_name property preserves the original casing."""
    canonical = normalize_entity_name(name)
    return canonical.lower() if canonical else ""


def normalize_entity_type(raw: str) -> str:
    """Map extraction output to canonical entity label (Neo4j node label)."""
    if not raw or not isinstance(raw, str):
        return "Thing"
    key = raw.strip().replace(" ", "_").replace("-", "_").lower()  # Fix: was replace("-","") → "agerelated_change"
    return ENTITY_TYPE_ALIASES.get(key) or raw.replace(" ", "_").replace("/", "_").capitalize()


def normalize_predicate(raw: str) -> str:
    """Map extraction output to canonical predicate (Neo4j relationship type)."""
    if not raw or not isinstance(raw, str):
        return "RELATES_TO"
    p = raw.strip().upper().replace(" ", "_").replace("-", "_")
    return p if p in ALL_PREDICATES else "RELATES_TO"  # Fix: was returning p in both branches (no-op)


def get_ontology_prompt_section(include_aging: bool = True) -> str:
    """Return the ontology section for the extraction prompt (entity types + relationship types).
    When include_aging=True, BodySystem, AgeRelatedChange, LifeStage and aging predicates are included (docs/AGING_AND_HUMAN_BIOLOGY.md).
    """
    entity_list = "\n".join(f"- {t}" for t in (ENTITY_TYPES if include_aging else ENTITY_TYPES[:6]))
    preds = ALL_PREDICATES if include_aging else PREDICATES
    pred_list = "\n".join(f"- {p}" for p in preds)
    return f"""
Target Entity Types (use exactly these labels):
{entity_list}

Target Relationship Types (use exactly these; one per triple):
{pred_list}

Return ONLY triples whose subject_type and object_type are from the Entity Types list and whose predicate is from the Relationship Types list.
If the text discusses aging, life stage, body systems, or modifiable risk, use types like AgeRelatedChange, LifeStage, BodySystem and predicates like PART_OF, OCCURS_AT, INCREASES_RISK_OF, MODIFIABLE_BY, EXPLAINS_WHY where supported.
For early signals: use Symptom -EARLY_SIGNAL_OF-> Disease when the text describes early signs/symptoms of a disease; use ALLEVIATES (food/nutrient reduces symptom) and AGGRAVATES (food/nutrient worsens symptom) so we can recommend "foods that reduce" vs "foods to avoid".
"""
