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
