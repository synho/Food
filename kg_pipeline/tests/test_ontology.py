"""Tests for kg_pipeline/src/ontology.py — normalization functions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ontology import (
    normalize_entity_name,
    normalize_entity_type,
    normalize_predicate,
    ALL_PREDICATES,
    ENTITY_TYPES,
    CANONICAL_ENTITY_NAMES,
    REJECT_ENTITY_TYPES,
    WEAK_PREDICATES,
    _PREDICATE_ALIASES,
)


# ── normalize_entity_name ─────────────────────────────────────────────────────

class TestNormalizeEntityName:
    def test_canonical_lookup_lowercase(self):
        assert normalize_entity_name("vitamin d") == "Vitamin D"

    def test_canonical_lookup_mixed_case(self):
        assert normalize_entity_name("Vitamin D") == "Vitamin D"

    def test_alias_t2dm(self):
        assert normalize_entity_name("t2dm") == "Type 2 diabetes"

    def test_alias_tirzepatide(self):
        assert normalize_entity_name("tirzepatide") == "Mounjaro"

    def test_passthrough_unknown(self):
        assert normalize_entity_name("Broccoli") == "Broccoli"

    def test_strips_whitespace(self):
        assert normalize_entity_name("  omega-3  ") == "Omega-3"

    def test_empty_string(self):
        assert normalize_entity_name("") == ""

    def test_none_returns_empty(self):
        assert normalize_entity_name(None) == ""

    def test_high_blood_pressure(self):
        assert normalize_entity_name("high blood pressure") == "Hypertension"

    def test_pre_diabetes_variants(self):
        for variant in ("pre diabetes", "pre-diabetes", "pre diabetic", "pre diabetics"):
            assert normalize_entity_name(variant) == "Prediabetes", f"Failed for '{variant}'"

    # ── Common foods ──────────────────────────────────────────────────────
    def test_food_oatmeal_to_oats(self):
        assert normalize_entity_name("oatmeal") == "Oats"

    def test_food_yoghurt_to_yogurt(self):
        assert normalize_entity_name("yoghurt") == "Yogurt"

    def test_food_olive_oil_variants(self):
        assert normalize_entity_name("olive oil") == "Olive oil"
        assert normalize_entity_name("extra virgin olive oil") == "Olive oil"
        assert normalize_entity_name("evoo") == "Olive oil"

    def test_food_singular_plural(self):
        assert normalize_entity_name("blueberry") == "Blueberries"
        assert normalize_entity_name("walnut") == "Walnuts"
        assert normalize_entity_name("lentil") == "Lentils"
        assert normalize_entity_name("tomato") == "Tomatoes"

    # ── Nutrients ─────────────────────────────────────────────────────────
    def test_fiber_variants(self):
        for variant in ("fiber", "fibre", "dietary fiber", "dietary fibre"):
            assert normalize_entity_name(variant) == "Dietary fiber", f"Failed for '{variant}'"

    def test_b12_variants(self):
        assert normalize_entity_name("b12") == "Vitamin B12"
        assert normalize_entity_name("vitamin b12") == "Vitamin B12"
        assert normalize_entity_name("cobalamin") == "Vitamin B12"

    def test_folate_variants(self):
        assert normalize_entity_name("folic acid") == "Folate"
        assert normalize_entity_name("folate") == "Folate"

    def test_coq10_variants(self):
        assert normalize_entity_name("coq10") == "Coenzyme Q10"
        assert normalize_entity_name("coenzyme q10") == "Coenzyme Q10"

    def test_omega6(self):
        assert normalize_entity_name("omega-6") == "Omega-6"
        assert normalize_entity_name("omega 6") == "Omega-6"

    # ── Dietary patterns ──────────────────────────────────────────────────
    def test_keto_variants(self):
        assert normalize_entity_name("keto") == "Ketogenic diet"
        assert normalize_entity_name("keto diet") == "Ketogenic diet"
        assert normalize_entity_name("ketogenic diet") == "Ketogenic diet"

    def test_dash_diet(self):
        assert normalize_entity_name("dash diet") == "DASH diet"

    def test_plant_based_diet(self):
        assert normalize_entity_name("plant-based diet") == "Plant-based diet"
        assert normalize_entity_name("plant based diet") == "Plant-based diet"

    def test_vegan_shorthand(self):
        assert normalize_entity_name("vegan") == "Vegan diet"

    # ── General health conditions ─────────────────────────────────────────
    def test_ibs(self):
        assert normalize_entity_name("ibs") == "Irritable bowel syndrome"

    def test_gerd_variants(self):
        assert normalize_entity_name("gerd") == "Gastroesophageal reflux disease"
        assert normalize_entity_name("acid reflux") == "Gastroesophageal reflux disease"

    def test_nafld_variants(self):
        assert normalize_entity_name("nafld") == "Non-alcoholic fatty liver disease"
        assert normalize_entity_name("fatty liver") == "Non-alcoholic fatty liver disease"

    def test_iron_deficiency_variants(self):
        assert normalize_entity_name("iron deficiency anemia") == "Iron-deficiency anaemia"
        assert normalize_entity_name("iron-deficiency anaemia") == "Iron-deficiency anaemia"


# ── normalize_entity_type ─────────────────────────────────────────────────────

class TestNormalizeEntityType:
    def test_disease(self):
        assert normalize_entity_type("disease") == "Disease"

    def test_food(self):
        assert normalize_entity_type("food") == "Food"

    def test_drug_slash_treatment(self):
        assert normalize_entity_type("drug/treatment") == "Drug"

    def test_lifestyle_factor_with_space(self):
        assert normalize_entity_type("lifestyle factor") == "LifestyleFactor"

    def test_age_related_change(self):
        assert normalize_entity_type("age related change") == "AgeRelatedChange"

    def test_unknown_returns_capitalized(self):
        result = normalize_entity_type("unknown_thing")
        assert result  # Should return something non-empty
        assert result[0].isupper()

    def test_empty_returns_thing(self):
        assert normalize_entity_type("") == "Thing"

    def test_single_word_types_roundtrip(self):
        # Single-word entity types survive lowercase → normalize because their aliases are registered.
        # Multi-word PascalCase types (AgeRelatedChange, LifestyleFactor, etc.) are accessed via
        # their phrase forms ("age related change", "lifestyle factor") not via PascalCase lowercased.
        single_word_types = ["Disease", "Symptom", "Food", "Nutrient", "Drug", "Study"]
        for t in single_word_types:
            result = normalize_entity_type(t.lower())
            assert result == t, f"Roundtrip failed for '{t}': got '{result}'"

    def test_phrase_forms_of_multi_word_types(self):
        # Multi-word types are accessed via their canonical phrase aliases
        assert normalize_entity_type("age related change") == "AgeRelatedChange"
        assert normalize_entity_type("age_related_change") == "AgeRelatedChange"
        assert normalize_entity_type("lifestyle factor") == "LifestyleFactor"
        assert normalize_entity_type("life stage") == "LifeStage"
        assert normalize_entity_type("body system") == "BodySystem"


# ── normalize_predicate ───────────────────────────────────────────────────────

class TestNormalizePredicate:
    def test_prevents(self):
        assert normalize_predicate("prevents") == "PREVENTS"

    def test_causes_uppercase(self):
        assert normalize_predicate("CAUSES") == "CAUSES"

    def test_with_spaces(self):
        assert normalize_predicate("reduces risk of") == "REDUCES_RISK_OF"

    def test_early_signal_of(self):
        assert normalize_predicate("early_signal_of") == "EARLY_SIGNAL_OF"

    def test_unknown_returns_relates_to(self):
        assert normalize_predicate("nonsense") == "RELATES_TO"

    def test_empty_returns_relates_to(self):
        assert normalize_predicate("") == "RELATES_TO"

    def test_all_predicates_roundtrip(self):
        for p in ALL_PREDICATES:
            result = normalize_predicate(p)
            assert result == p, f"Roundtrip failed for '{p}': got '{result}'"


# ── CANONICAL_ENTITY_NAMES integrity ─────────────────────────────────────────

class TestCanonicalNames:
    def test_all_keys_are_lowercase(self):
        for k in CANONICAL_ENTITY_NAMES:
            assert k == k.lower(), f"Key '{k}' is not lowercase"

    def test_all_values_are_nonempty_strings(self):
        for k, v in CANONICAL_ENTITY_NAMES.items():
            assert isinstance(v, str) and v, f"Value for '{k}' is empty or not a string"


# ── Non-standard type aliases (Phase 1B) ────────────────────────────────────

class TestNonStandardTypeAliases:
    """Verify the 22 non-standard types found in audit map correctly."""

    def test_cell_to_bodysystem(self):
        assert normalize_entity_type("Cell") == "BodySystem"
        assert normalize_entity_type("CellType") == "BodySystem"
        assert normalize_entity_type("CellPopulation") == "BodySystem"

    def test_intervention_to_drug(self):
        assert normalize_entity_type("Intervention") == "Drug"

    def test_cognitive_function_to_symptom(self):
        assert normalize_entity_type("Cognitive_Function") == "Symptom"
        assert normalize_entity_type("cognitive function") == "Symptom"

    def test_device_dosage_procedure_to_drug(self):
        assert normalize_entity_type("Device") == "Drug"
        assert normalize_entity_type("Dosage") == "Drug"
        assert normalize_entity_type("Procedure") == "Drug"

    def test_chemical_to_nutrient(self):
        assert normalize_entity_type("Chemical") == "Nutrient"

    def test_nutrient_deficiency_to_disease(self):
        assert normalize_entity_type("Nutrient_Deficiency") == "Disease"
        assert normalize_entity_type("nutrient deficiency") == "Disease"

    def test_variant_to_biomarker(self):
        assert normalize_entity_type("Variant") == "Biomarker"

    def test_adverse_event_to_symptom(self):
        assert normalize_entity_type("Adverse_Event") == "Symptom"
        assert normalize_entity_type("adverse event") == "Symptom"

    def test_lifestage_related_change(self):
        assert normalize_entity_type("LifestageRelatedChange") == "AgeRelatedChange"

    def test_property_to_biomarker(self):
        assert normalize_entity_type("Property") == "Biomarker"


# ── Reject entity types ─────────────────────────────────────────────────────

class TestRejectEntityTypes:
    """Types that should be rejected outright (returns None)."""

    def test_task_rejected(self):
        assert normalize_entity_type("Task") is None

    def test_technology_rejected(self):
        assert normalize_entity_type("Technology") is None

    def test_organism_rejected(self):
        assert normalize_entity_type("Organism") is None

    def test_algorithm_rejected(self):
        assert normalize_entity_type("Algorithm") is None

    def test_material_rejected(self):
        assert normalize_entity_type("Material") is None

    def test_pathogen_rejected(self):
        assert normalize_entity_type("Pathogen") is None

    def test_healthcare_facility_rejected(self):
        assert normalize_entity_type("HealthcareFacility") is None
        assert normalize_entity_type("healthcare facility") is None


# ── Predicate aliases (Phase 2B) ────────────────────────────────────────────

class TestPredicateAliases:
    """Verify LLM near-miss predicates are mapped to canonical predicates."""

    def test_worsens_to_aggravates(self):
        assert normalize_predicate("WORSENS") == "AGGRAVATES"

    def test_improves_to_alleviates(self):
        assert normalize_predicate("IMPROVES") == "ALLEVIATES"

    def test_inhibits_to_targets_mechanism(self):
        assert normalize_predicate("INHIBITS") == "TARGETS_MECHANISM"

    def test_activates_to_targets_mechanism(self):
        assert normalize_predicate("ACTIVATES") == "TARGETS_MECHANISM"

    def test_modulates_to_targets_mechanism(self):
        assert normalize_predicate("MODULATES") == "TARGETS_MECHANISM"

    def test_promotes_to_increases_risk(self):
        assert normalize_predicate("PROMOTES") == "INCREASES_RISK_OF"

    def test_suppresses_to_reduces_risk(self):
        assert normalize_predicate("SUPPRESSES") == "REDUCES_RISK_OF"

    def test_mitigates_to_alleviates(self):
        assert normalize_predicate("MITIGATES") == "ALLEVIATES"

    def test_exacerbates_to_aggravates(self):
        assert normalize_predicate("EXACERBATES") == "AGGRAVATES"

    def test_protects_against_to_prevents(self):
        assert normalize_predicate("PROTECTS_AGAINST") == "PREVENTS"

    def test_is_component_of_to_contains(self):
        assert normalize_predicate("IS_COMPONENT_OF") == "CONTAINS"

    def test_marker_for_to_biomarker_for(self):
        assert normalize_predicate("MARKER_FOR") == "BIOMARKER_FOR"

    def test_indicates_to_biomarker_for(self):
        assert normalize_predicate("INDICATES") == "BIOMARKER_FOR"

    def test_lowercase_alias(self):
        assert normalize_predicate("worsens") == "AGGRAVATES"
        assert normalize_predicate("improves") == "ALLEVIATES"

    def test_all_alias_targets_are_valid_predicates(self):
        """Every alias target must be in ALL_PREDICATES."""
        all_set = set(ALL_PREDICATES)
        for alias, target in _PREDICATE_ALIASES.items():
            assert target in all_set, f"Alias '{alias}' → '{target}' is not in ALL_PREDICATES"


# ── Microbiome/Metabolite layer ──────────────────────────────────────────────

class TestMicrobiomeMetaboliteLayer:
    def test_microbiome_entity_type_direct(self):
        assert normalize_entity_type("Microbiome") == "Microbiome"

    def test_microbiome_entity_type_alias(self):
        assert normalize_entity_type("microbiome") == "Microbiome"
        assert normalize_entity_type("gut bacteria") == "Microbiome"
        assert normalize_entity_type("microbial species") == "Microbiome"

    def test_metabolite_entity_type_direct(self):
        assert normalize_entity_type("Metabolite") == "Metabolite"

    def test_metabolite_entity_type_alias(self):
        assert normalize_entity_type("metabolite") == "Metabolite"
        assert normalize_entity_type("microbial metabolite") == "Metabolite"
        assert normalize_entity_type("scfa") == "Metabolite"
        assert normalize_entity_type("postbiotic") == "Metabolite"

    def test_produces_in_all_predicates(self):
        assert "PRODUCES" in ALL_PREDICATES

    def test_produces_normalize(self):
        assert normalize_predicate("PRODUCES") == "PRODUCES"
        assert normalize_predicate("GENERATES") == "PRODUCES"
        assert normalize_predicate("FERMENTS_TO") == "PRODUCES"

    def test_modulates_microbiome_in_all_predicates(self):
        assert "MODULATES_MICROBIOME" in ALL_PREDICATES

    def test_modulates_microbiome_normalize(self):
        assert normalize_predicate("MODULATES_MICROBIOME") == "MODULATES_MICROBIOME"
        assert normalize_predicate("ENRICHES") == "MODULATES_MICROBIOME"
        assert normalize_predicate("DEPLETES") == "MODULATES_MICROBIOME"

    def test_microbiome_canonical_akkermansia(self):
        assert normalize_entity_name("akkermansia") == "Akkermansia muciniphila"
        assert normalize_entity_name("akkermansia muciniphila") == "Akkermansia muciniphila"

    def test_metabolite_canonical_butyrate(self):
        assert normalize_entity_name("butyrate") == "Butyrate"
        assert normalize_entity_name("butyric acid") == "Butyrate"

    def test_metabolite_canonical_scfa(self):
        assert normalize_entity_name("scfa") == "Short-chain fatty acids"
        assert normalize_entity_name("short chain fatty acids") == "Short-chain fatty acids"

    def test_metabolite_canonical_tmao(self):
        assert normalize_entity_name("tmao") == "TMAO"
        assert normalize_entity_name("trimethylamine n-oxide") == "TMAO"

    def test_metabolite_canonical_urolithin(self):
        assert normalize_entity_name("urolithin") == "Urolithin A"
        assert normalize_entity_name("urolithin a") == "Urolithin A"


# ── Weak predicates ─────────────────────────────────────────────────────────

class TestWeakPredicates:
    def test_ambiguous_predicates_fall_through_to_relates_to(self):
        # These should normalize to RELATES_TO (not in ALL_PREDICATES, not in aliases)
        assert normalize_predicate("ASSOCIATED_WITH") == "RELATES_TO"
        assert normalize_predicate("LINKED_TO") == "RELATES_TO"
        assert normalize_predicate("CORRELATED_WITH") == "RELATES_TO"

    def test_weak_predicates_set_contents(self):
        assert "RELATES_TO" in WEAK_PREDICATES
        assert "AFFECTS" in WEAK_PREDICATES
        assert "ASSOCIATED_WITH" in WEAK_PREDICATES
        assert "LINKED_TO" in WEAK_PREDICATES
        assert "CORRELATED_WITH" in WEAK_PREDICATES
