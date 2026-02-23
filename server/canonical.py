"""
Canonical entity names for API and KG queries. Keep in sync with kg_pipeline/src/ontology.py.
All terms must be standardized; use these when normalizing user input (e.g. conditions, symptoms).
"""
# SYNC: keep in sync with kg_pipeline/src/ontology.py CANONICAL_ENTITY_NAMES.
# This file is the server-side source of truth; ontology.py mirrors it for pipeline normalization.
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
}


def normalize_entity_name(name: str) -> str:
    """Return canonical form for KG lookup. Use for conditions, symptoms, food names."""
    if not name or not isinstance(name, str):
        return name or ""
    key = name.strip().lower()
    return CANONICAL_ENTITY_NAMES.get(key) or name.strip()
