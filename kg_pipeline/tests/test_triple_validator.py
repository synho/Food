"""Tests for kg_pipeline/src/triple_validator.py — validation and scoring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from triple_validator import validate_and_score, _is_vague, _ABBREVIATION_WHITELIST


def _make_triple(**overrides):
    """Create a valid base triple, overriding any fields."""
    base = {
        "subject": "Salmon",
        "subject_type": "Food",
        "predicate": "PREVENTS",
        "object": "Cardiovascular disease",
        "object_type": "Disease",
        "source_id": "PMC001",
        "pub_date": "2024-01",
        "context": "Salmon prevents cardiovascular disease.",
        "journal": "JAMA",
        "evidence_type": "",
    }
    base.update(overrides)
    return base


# ── Abbreviation whitelist ───────────────────────────────────────────────────

class TestAbbreviationWhitelist:
    def test_ra_not_vague(self):
        assert not _is_vague("RA")

    def test_ms_not_vague(self):
        assert not _is_vague("MS")

    def test_uc_not_vague(self):
        assert not _is_vague("UC")

    def test_oa_not_vague(self):
        assert not _is_vague("OA")

    def test_mi_not_vague(self):
        assert not _is_vague("MI")

    def test_crp_not_vague(self):
        assert not _is_vague("CRP")

    def test_ldl_not_vague(self):
        assert not _is_vague("LDL")

    def test_hdl_not_vague(self):
        assert not _is_vague("HDL")

    def test_bmi_not_vague(self):
        assert not _is_vague("BMI")

    def test_copd_not_vague(self):
        assert not _is_vague("COPD")

    def test_single_char_still_vague(self):
        assert _is_vague("A")

    def test_two_char_non_whitelisted_still_vague(self):
        assert _is_vague("AB")

    def test_empty_still_vague(self):
        assert _is_vague("")

    def test_known_vague_term_still_vague(self):
        assert _is_vague("patients")

    def test_abbreviation_triple_passes_validation(self):
        """A triple with whitelisted abbreviation as subject should pass."""
        t = _make_triple(subject="RA")
        valid, rejected, stats = validate_and_score([t])
        assert len(valid) == 1
        assert len(rejected) == 0

    def test_abbreviation_triple_as_object_passes(self):
        t = _make_triple(object="CRP")
        valid, rejected, stats = validate_and_score([t])
        assert len(valid) == 1


# ── Reject entity types in validator ─────────────────────────────────────────

class TestRejectEntityTypes:
    def test_task_type_rejected(self):
        t = _make_triple(subject_type="Task")
        # After normalize_entity_type, Task → None, but in validator the raw type is checked
        # The validator checks the raw string against REJECT_ENTITY_TYPES
        t["subject_type"] = "Task"
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1
        assert "rejected subject_type" in rejected[0]["_reject_reason"]

    def test_technology_type_rejected(self):
        t = _make_triple(object_type="Technology")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1
        assert "rejected object_type" in rejected[0]["_reject_reason"]


# ── Weak predicate filtering ────────────────────────────────────────────────

class TestWeakPredicateFilter:
    def test_relates_to_rejected(self):
        t = _make_triple(predicate="RELATES_TO")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1

    def test_affects_rejected(self):
        t = _make_triple(predicate="AFFECTS")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1

    def test_associated_with_rejected(self):
        t = _make_triple(predicate="ASSOCIATED_WITH")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1

    def test_linked_to_rejected(self):
        t = _make_triple(predicate="LINKED_TO")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1

    def test_correlated_with_rejected(self):
        t = _make_triple(predicate="CORRELATED_WITH")
        valid, rejected, stats = validate_and_score([t])
        assert len(rejected) == 1

    def test_prevents_accepted(self):
        t = _make_triple(predicate="PREVENTS")
        valid, rejected, stats = validate_and_score([t])
        assert len(valid) == 1
