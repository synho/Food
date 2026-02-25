"""Tests for medical KG layer — entity types, predicates, and canonical names."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ontology import (
    normalize_entity_name,
    normalize_entity_type,
    normalize_predicate,
    ALL_PREDICATES,
    ENTITY_TYPES,
    PREDICATES_MEDICAL,
    CANONICAL_ENTITY_NAMES,
)


# ── Medical entity types ─────────────────────────────────────────────────────

class TestMedicalEntityTypes:
    def test_biomarker_in_entity_types(self):
        assert "Biomarker" in ENTITY_TYPES

    def test_clinical_trial_in_entity_types(self):
        assert "ClinicalTrial" in ENTITY_TYPES

    def test_mechanism_in_entity_types(self):
        assert "Mechanism" in ENTITY_TYPES

    def test_biochemical_pathway_in_entity_types(self):
        assert "BiochemicalPathway" in ENTITY_TYPES

    def test_population_group_in_entity_types(self):
        assert "PopulationGroup" in ENTITY_TYPES

    def test_entity_type_count(self):
        assert len(ENTITY_TYPES) == 15


class TestMedicalEntityTypeNormalization:
    def test_biomarker(self):
        assert normalize_entity_type("biomarker") == "Biomarker"

    def test_clinical_trial_phrase(self):
        assert normalize_entity_type("clinical trial") == "ClinicalTrial"

    def test_clinical_trial_underscore(self):
        assert normalize_entity_type("clinical_trial") == "ClinicalTrial"

    def test_mechanism(self):
        assert normalize_entity_type("mechanism") == "Mechanism"

    def test_biochemical_pathway_phrase(self):
        assert normalize_entity_type("biochemical pathway") == "BiochemicalPathway"

    def test_pathway_alias(self):
        assert normalize_entity_type("pathway") == "BiochemicalPathway"

    def test_population_group_phrase(self):
        assert normalize_entity_type("population group") == "PopulationGroup"

    def test_population_alias(self):
        assert normalize_entity_type("population") == "PopulationGroup"

    def test_trial_alias(self):
        assert normalize_entity_type("trial") == "ClinicalTrial"


# ── Medical predicates ───────────────────────────────────────────────────────

class TestMedicalPredicates:
    def test_medical_predicates_in_all(self):
        for p in PREDICATES_MEDICAL:
            assert p in ALL_PREDICATES, f"{p} not in ALL_PREDICATES"

    def test_biomarker_for(self):
        assert normalize_predicate("biomarker_for") == "BIOMARKER_FOR"

    def test_increases_biomarker(self):
        assert normalize_predicate("increases_biomarker") == "INCREASES_BIOMARKER"

    def test_decreases_biomarker(self):
        assert normalize_predicate("decreases_biomarker") == "DECREASES_BIOMARKER"

    def test_contraindicated_with(self):
        assert normalize_predicate("contraindicated_with") == "CONTRAINDICATED_WITH"

    def test_targets_mechanism(self):
        assert normalize_predicate("targets_mechanism") == "TARGETS_MECHANISM"

    def test_studied_in(self):
        assert normalize_predicate("studied_in") == "STUDIED_IN"

    def test_all_medical_predicates_roundtrip(self):
        for p in PREDICATES_MEDICAL:
            assert normalize_predicate(p) == p, f"Roundtrip failed for '{p}'"

    def test_predicate_count(self):
        assert len(ALL_PREDICATES) == 22


# ── Medical canonical names — Biomarkers ─────────────────────────────────────

class TestBiomarkerCanonicalNames:
    def test_hba1c_variants(self):
        for variant in ("hba1c", "hemoglobin a1c", "glycated hemoglobin", "a1c"):
            assert normalize_entity_name(variant) == "HbA1c", f"Failed for '{variant}'"

    def test_ldl_variants(self):
        for variant in ("ldl", "ldl cholesterol", "ldl-c", "low-density lipoprotein"):
            assert normalize_entity_name(variant) == "LDL cholesterol", f"Failed for '{variant}'"

    def test_hdl_variants(self):
        assert normalize_entity_name("hdl") == "HDL cholesterol"
        assert normalize_entity_name("hdl-c") == "HDL cholesterol"

    def test_crp_variants(self):
        for variant in ("crp", "c-reactive protein", "hs-crp"):
            assert normalize_entity_name(variant) == "C-reactive protein", f"Failed for '{variant}'"

    def test_egfr(self):
        assert normalize_entity_name("egfr") == "eGFR"
        assert normalize_entity_name("estimated glomerular filtration rate") == "eGFR"

    def test_triglycerides(self):
        assert normalize_entity_name("triglycerides") == "Triglycerides"
        assert normalize_entity_name("tg") == "Triglycerides"

    def test_fasting_glucose(self):
        assert normalize_entity_name("fasting glucose") == "Fasting glucose"
        assert normalize_entity_name("fbg") == "Fasting glucose"

    def test_bmi(self):
        assert normalize_entity_name("bmi") == "BMI"
        assert normalize_entity_name("body mass index") == "BMI"

    def test_homa_ir(self):
        assert normalize_entity_name("homa-ir") == "HOMA-IR"
        assert normalize_entity_name("homa ir") == "HOMA-IR"


# ── Medical canonical names — Mechanisms ─────────────────────────────────────

class TestMechanismCanonicalNames:
    def test_insulin_resistance(self):
        assert normalize_entity_name("insulin resistance") == "Insulin resistance"

    def test_gut_brain_axis(self):
        assert normalize_entity_name("gut-brain axis") == "Gut-brain axis"
        assert normalize_entity_name("gut brain axis") == "Gut-brain axis"

    def test_neuroinflammation(self):
        assert normalize_entity_name("neuroinflammation") == "Neuroinflammation"

    def test_ampk(self):
        assert normalize_entity_name("ampk") == "AMPK activation"
        assert normalize_entity_name("ampk activation") == "AMPK activation"

    def test_mtor(self):
        assert normalize_entity_name("mtor") == "mTOR signaling"

    def test_sirtuin(self):
        assert normalize_entity_name("sirt1") == "Sirtuin activation"

    def test_nfkb(self):
        assert normalize_entity_name("nf-kb") == "NF-kB signaling"

    def test_autophagy(self):
        assert normalize_entity_name("autophagy") == "Autophagy"

    def test_microbiome(self):
        assert normalize_entity_name("microbiome") == "Gut microbiome modulation"


# ── Medical canonical names — Clinical Trials ────────────────────────────────

class TestClinicalTrialCanonicalNames:
    def test_predimed(self):
        assert normalize_entity_name("predimed") == "PREDIMED trial"
        assert normalize_entity_name("predimed trial") == "PREDIMED trial"

    def test_dash_trial(self):
        assert normalize_entity_name("dash trial") == "DASH trial"

    def test_framingham(self):
        assert normalize_entity_name("framingham") == "Framingham Heart Study"

    def test_epic(self):
        assert normalize_entity_name("epic") == "EPIC study"

    def test_whi(self):
        assert normalize_entity_name("whi") == "Women's Health Initiative"


# ── Medical canonical names — Population Groups ──────────────────────────────

class TestPopulationGroupCanonicalNames:
    def test_postmenopausal_women(self):
        assert normalize_entity_name("postmenopausal women") == "Postmenopausal women"

    def test_elderly_adults(self):
        assert normalize_entity_name("elderly adults") == "Elderly adults"
        assert normalize_entity_name("older adults") == "Elderly adults"


# ── Medical canonical names — Biochemical Pathways ───────────────────────────

class TestBiochemicalPathwayCanonicalNames:
    def test_krebs_cycle(self):
        assert normalize_entity_name("krebs cycle") == "Citric acid cycle"
        assert normalize_entity_name("tca cycle") == "Citric acid cycle"

    def test_beta_oxidation(self):
        assert normalize_entity_name("beta oxidation") == "Fatty acid oxidation"

    def test_mevalonate(self):
        assert normalize_entity_name("mevalonate pathway") == "Cholesterol biosynthesis"


# ── Existing canonical names still work ──────────────────────────────────────

class TestExistingNamesUnbroken:
    """Ensure the medical additions didn't break existing canonical names."""

    def test_vitamin_d(self):
        assert normalize_entity_name("vitamin d") == "Vitamin D"

    def test_type_2_diabetes(self):
        assert normalize_entity_name("t2dm") == "Type 2 diabetes"

    def test_omega_3(self):
        assert normalize_entity_name("omega-3") == "Omega-3"

    def test_dash_diet_still_works(self):
        """DASH diet (food ontology) is separate from DASH trial (medical ontology)."""
        assert normalize_entity_name("dash diet") == "DASH diet"

    def test_chronic_inflammation(self):
        assert normalize_entity_name("chronic inflammation") == "Chronic inflammation"

    def test_oxidative_stress(self):
        assert normalize_entity_name("oxidative stress") == "Oxidative stress"
