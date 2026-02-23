"""Tests for kg_pipeline/src/consolidate_graph.py — merge and dedup logic."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _write_triples(dir_path: str, filename: str, triples: list) -> str:
    path = os.path.join(dir_path, filename)
    with open(path, "w") as f:
        json.dump(triples, f)
    return path


class TestConsolidateGraph:
    def test_merges_multiple_triple_files(self):
        """All triples from separate *_triples.json files are combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_triples(tmpdir, "paper1_triples.json", [
                {"subject": "Salmon", "predicate": "PREVENTS", "object": "Cardiovascular disease",
                 "source_id": "PMC001", "pub_date": "2024-01"}
            ])
            _write_triples(tmpdir, "paper2_triples.json", [
                {"subject": "Broccoli", "predicate": "REDUCES_RISK_OF", "object": "Type 2 diabetes",
                 "source_id": "PMC002", "pub_date": "2024-02"},
                {"subject": "Vitamin D", "predicate": "TREATS", "object": "Osteoporosis",
                 "source_id": "PMC002", "pub_date": "2024-02"},
            ])
            output_file = os.path.join(tmpdir, "master_graph.json")

            paths_cfg = {"extracted_triples": tmpdir, "master_graph": output_file}
            with patch("consolidate_graph.get_paths_config", return_value=paths_cfg):
                from consolidate_graph import consolidate_graph
                result_path = consolidate_graph()

            with open(result_path) as f:
                merged = json.load(f)

            assert len(merged) == 3
            source_ids = {t["source_id"] for t in merged}
            assert source_ids == {"PMC001", "PMC002"}

    def test_empty_directory_produces_empty_master(self):
        """No triple files → master_graph.json is an empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "master_graph.json")
            paths_cfg = {"extracted_triples": tmpdir, "master_graph": output_file}
            with patch("consolidate_graph.get_paths_config", return_value=paths_cfg):
                from consolidate_graph import consolidate_graph
                result_path = consolidate_graph()

            with open(result_path) as f:
                merged = json.load(f)

            assert merged == []

    def test_master_graph_file_is_not_included_in_merge(self):
        """master_graph.json itself should not be re-read as a triple file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-existing master_graph.json (from a previous run)
            _write_triples(tmpdir, "master_graph.json", [
                {"subject": "old", "predicate": "CAUSES", "object": "noise",
                 "source_id": "OLD", "pub_date": "2023-01"}
            ])
            _write_triples(tmpdir, "new_triples.json", [
                {"subject": "Salmon", "predicate": "PREVENTS", "object": "Hypertension",
                 "source_id": "PMC003", "pub_date": "2024-03"}
            ])
            output_file = os.path.join(tmpdir, "master_graph.json")
            paths_cfg = {"extracted_triples": tmpdir, "master_graph": output_file}
            with patch("consolidate_graph.get_paths_config", return_value=paths_cfg):
                from consolidate_graph import consolidate_graph
                consolidate_graph()

            with open(output_file) as f:
                merged = json.load(f)

            # Only new_triples.json should be included; master_graph.json uses glob *_triples.json
            subjects = [t["subject"] for t in merged]
            assert "Salmon" in subjects
            assert "old" not in subjects

    def test_returns_output_file_path(self):
        """consolidate_graph() returns the path to the master file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "master_graph.json")
            paths_cfg = {"extracted_triples": tmpdir, "master_graph": output_file}
            with patch("consolidate_graph.get_paths_config", return_value=paths_cfg):
                from consolidate_graph import consolidate_graph
                result = consolidate_graph()

            assert result == output_file
