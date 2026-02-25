"""Tests for medical triple extraction — mock LLM responses, verify normalization and validation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ontology import (
    normalize_entity_type,
    normalize_entity_name,
    normalize_predicate,
    get_ontology_prompt_section,
)


class TestMedicalExtractionPrompt:
    """Verify that the extraction prompt includes medical instructions."""

    def test_prompt_includes_biomarker_instructions(self):
        prompt = get_ontology_prompt_section()
        assert "INCREASES_BIOMARKER" in prompt
        assert "DECREASES_BIOMARKER" in prompt
        assert "Biomarker" in prompt

    def test_prompt_includes_mechanism_instructions(self):
        prompt = get_ontology_prompt_section()
        assert "TARGETS_MECHANISM" in prompt
        assert "Mechanism" in prompt

    def test_prompt_includes_contraindication_instructions(self):
        prompt = get_ontology_prompt_section()
        assert "CONTRAINDICATED_WITH" in prompt

    def test_prompt_includes_clinical_trial_instructions(self):
        prompt = get_ontology_prompt_section()
        assert "ClinicalTrial" in prompt
        assert "STUDIED_IN" in prompt

    def test_prompt_includes_all_medical_entity_types(self):
        prompt = get_ontology_prompt_section()
        for t in ["Biomarker", "ClinicalTrial", "Mechanism", "BiochemicalPathway", "PopulationGroup"]:
            assert t in prompt, f"Missing entity type {t} in prompt"


class TestMockBiomarkerTriple:
    """Simulate a biomarker triple from LLM and verify normalization."""

    def _normalize_triple(self, raw: dict) -> dict:
        """Apply the same normalization the pipeline uses."""
        return {
            "subject": normalize_entity_name(raw.get("subject", "")),
            "subject_type": normalize_entity_type(raw.get("subject_type", "")),
            "predicate": normalize_predicate(raw.get("predicate", "")),
            "object": normalize_entity_name(raw.get("object", "")),
            "object_type": normalize_entity_type(raw.get("object_type", "")),
            "context": raw.get("context", ""),
            "source_id": raw.get("source_id", ""),
        }

    def test_omega3_decreases_ldl(self):
        raw = {
            "subject": "omega-3",
            "subject_type": "nutrient",
            "predicate": "decreases_biomarker",
            "object": "LDL",
            "object_type": "biomarker",
            "context": "Omega-3 supplementation reduced LDL cholesterol by 10%",
            "source_id": "12345678",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "Omega-3"
        assert t["subject_type"] == "Nutrient"
        assert t["predicate"] == "DECREASES_BIOMARKER"
        assert t["object"] == "LDL cholesterol"
        assert t["object_type"] == "Biomarker"

    def test_hba1c_biomarker_for_diabetes(self):
        raw = {
            "subject": "HbA1c",
            "subject_type": "biomarker",
            "predicate": "biomarker_for",
            "object": "type 2 diabetes",
            "object_type": "disease",
            "context": "HbA1c is the primary biomarker for Type 2 diabetes",
            "source_id": "87654321",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "HbA1c"
        assert t["subject_type"] == "Biomarker"
        assert t["predicate"] == "BIOMARKER_FOR"
        assert t["object"] == "Type 2 diabetes"
        assert t["object_type"] == "Disease"


class TestMockMechanismTriple:
    def _normalize_triple(self, raw: dict) -> dict:
        return {
            "subject": normalize_entity_name(raw.get("subject", "")),
            "subject_type": normalize_entity_type(raw.get("subject_type", "")),
            "predicate": normalize_predicate(raw.get("predicate", "")),
            "object": normalize_entity_name(raw.get("object", "")),
            "object_type": normalize_entity_type(raw.get("object_type", "")),
        }

    def test_curcumin_targets_inflammation(self):
        raw = {
            "subject": "curcumin",
            "subject_type": "nutrient",
            "predicate": "targets_mechanism",
            "object": "chronic inflammation",
            "object_type": "mechanism",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "Curcumin"
        assert t["predicate"] == "TARGETS_MECHANISM"
        assert t["object"] == "Chronic inflammation"
        assert t["object_type"] == "Mechanism"

    def test_insulin_resistance_causes_diabetes(self):
        raw = {
            "subject": "insulin resistance",
            "subject_type": "mechanism",
            "predicate": "increases_risk_of",
            "object": "t2dm",
            "object_type": "disease",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "Insulin resistance"
        assert t["predicate"] == "INCREASES_RISK_OF"
        assert t["object"] == "Type 2 diabetes"


class TestMockDrugInteractionTriple:
    def _normalize_triple(self, raw: dict) -> dict:
        return {
            "subject": normalize_entity_name(raw.get("subject", "")),
            "subject_type": normalize_entity_type(raw.get("subject_type", "")),
            "predicate": normalize_predicate(raw.get("predicate", "")),
            "object": normalize_entity_name(raw.get("object", "")),
            "object_type": normalize_entity_type(raw.get("object_type", "")),
        }

    def test_vitamin_k_contraindicated_warfarin(self):
        raw = {
            "subject": "vitamin k",
            "subject_type": "nutrient",
            "predicate": "contraindicated_with",
            "object": "Warfarin",
            "object_type": "drug",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "Vitamin K"
        assert t["subject_type"] == "Nutrient"
        assert t["predicate"] == "CONTRAINDICATED_WITH"
        assert t["object"] == "Warfarin"
        assert t["object_type"] == "Drug"


class TestMockClinicalTrialTriple:
    def _normalize_triple(self, raw: dict) -> dict:
        return {
            "subject": normalize_entity_name(raw.get("subject", "")),
            "subject_type": normalize_entity_type(raw.get("subject_type", "")),
            "predicate": normalize_predicate(raw.get("predicate", "")),
            "object": normalize_entity_name(raw.get("object", "")),
            "object_type": normalize_entity_type(raw.get("object_type", "")),
        }

    def test_predimed_studied_in_mediterranean(self):
        raw = {
            "subject": "PREDIMED",
            "subject_type": "clinical trial",
            "predicate": "studied_in",
            "object": "mediterranean adults",
            "object_type": "population group",
        }
        t = self._normalize_triple(raw)
        assert t["subject"] == "PREDIMED trial"
        assert t["subject_type"] == "ClinicalTrial"
        assert t["predicate"] == "STUDIED_IN"
        assert t["object"] == "Mediterranean adults"
        assert t["object_type"] == "PopulationGroup"
