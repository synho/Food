"""Integration tests for server services with mocked Neo4j."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add repo root to path so server package resolves
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _make_rec_row(food="Salmon", predicate="PREVENTS", target="Cardiovascular disease",
                  source_id="PMC001", context="Study context", journal="NEJM",
                  pub_date="2024-01", via_nutrient=None, source_type="PMC"):
    return {
        "food": food, "predicate": predicate, "target": target,
        "source_id": source_id, "context": context, "journal": journal,
        "pub_date": pub_date, "via_nutrient": via_nutrient, "source_type": source_type,
    }


# ── Recommendations ───────────────────────────────────────────────────────────

class TestGetRecommendations:
    def test_returns_only_items_with_evidence(self):
        rows = [_make_rec_row()]
        with patch("server.services.recommendations.run_query", return_value=rows):
            from server.services.recommendations import get_recommendations
            result = get_recommendations(conditions=["Cardiovascular disease"], symptoms=[], limit=20)

        assert len(result.recommended) > 0
        for item in result.recommended:
            assert len(item.evidence) > 0, "Every recommendation must have at least one evidence record"

    def test_free_plan_limits_to_5(self):
        rows = [_make_rec_row(food=f"Food{i}", source_id=f"PMC{i:03d}") for i in range(20)]
        with patch("server.services.recommendations.run_query", return_value=rows):
            from server.services.recommendations import get_recommendations
            result = get_recommendations(
                conditions=["Cardiovascular disease"], symptoms=[], limit=20, plan="free"
            )

        assert len(result.recommended) <= 5, (
            f"Free plan should return ≤5 items, got {len(result.recommended)}"
        )

    def test_paid_plan_not_limited_to_5(self):
        rows = [_make_rec_row(food=f"Food{i}", source_id=f"PMC{i:03d}") for i in range(20)]
        with patch("server.services.recommendations.run_query", return_value=rows):
            from server.services.recommendations import get_recommendations
            result = get_recommendations(
                conditions=["Cardiovascular disease"], symptoms=[], limit=20, plan="paid"
            )

        # Paid plan should return more than 5 (all 20 deduplicated by food/reason)
        assert len(result.recommended) > 5

    def test_empty_kg_returns_empty_lists(self):
        with patch("server.services.recommendations.run_query", return_value=[]):
            from server.services.recommendations import get_recommendations
            result = get_recommendations(conditions=["Type 2 diabetes"], symptoms=[], limit=20)

        assert result.recommended == []
        assert result.restricted == []

    def test_normalizes_condition_names(self):
        """t2dm and Type 2 diabetes should both query the KG as 'Type 2 diabetes'."""
        captured_params = {}

        def mock_run_query(q, params):
            captured_params.update(params)
            return []

        with patch("server.services.recommendations.run_query", side_effect=mock_run_query):
            from server.services.recommendations import get_recommendations
            get_recommendations(conditions=["t2dm"], symptoms=[], limit=20)

        assert "Type 2 diabetes" in captured_params.get("targets", []), (
            "t2dm should be normalized to 'Type 2 diabetes' before querying KG"
        )


# ── Safest Path ───────────────────────────────────────────────────────────────

class TestGetSafestPath:
    def test_returns_steps_with_evidence(self):
        rows = [_make_rec_row()]
        with patch("server.services.safest_path.run_query", return_value=rows):
            from server.services.safest_path import get_safest_path
            result = get_safest_path(conditions=["Cardiovascular disease"], symptoms=[], limit=10)

        for step in result.steps:
            assert len(step.evidence) > 0, "Every path step must have at least one evidence record"

    def test_free_plan_limits_steps(self):
        rows = [_make_rec_row(food=f"Food{i}", source_id=f"PMC{i:03d}") for i in range(20)]
        with patch("server.services.safest_path.run_query", return_value=rows):
            from server.services.safest_path import get_safest_path
            result = get_safest_path(
                conditions=["Cardiovascular disease"], symptoms=[], limit=10, plan="free"
            )

        # Free plan should get ≤ 3 increase steps (each step mentions ≤3 foods)
        if result.steps:
            increase_step = next((s for s in result.steps if s.action.startswith("Increase:")), None)
            if increase_step:
                foods = increase_step.action.replace("Increase:", "").strip().split(", ")
                assert len(foods) <= 3, f"Free plan increase step should list ≤3 foods, got {len(foods)}"

    def test_empty_conditions_still_queries(self):
        """Empty conditions should query KG without targets filter (all foods)."""
        with patch("server.services.safest_path.run_query", return_value=[]) as mock_q:
            from server.services.safest_path import get_safest_path
            result = get_safest_path(conditions=[], symptoms=[], limit=10)

        assert mock_q.called


# ── Position ──────────────────────────────────────────────────────────────────

class TestGetPosition:
    def test_returns_active_conditions_canonical(self):
        with patch("server.services.position.run_query", return_value=[]):
            from server.services.position import get_position
            result = get_position(conditions=["t2dm"], symptoms=[])

        assert "Type 2 diabetes" in result.active_conditions

    def test_nearby_risks_from_symptoms(self):
        rows = [{
            "symptom": "Fatigue", "disease": "Type 2 diabetes",
            "source_id": "PMC001", "context": "ctx", "journal": "NEJM",
            "pub_date": "2024-01", "source_type": "PMC",
        }]
        with patch("server.services.position.run_query", return_value=rows):
            from server.services.position import get_position
            result = get_position(conditions=[], symptoms=["Fatigue"])

        assert any(r.name == "Type 2 diabetes" for r in result.nearby_risks)
