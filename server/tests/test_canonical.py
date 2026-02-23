"""Tests that server/canonical.py stays in sync with kg_pipeline/src/ontology.py."""
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_pipeline_canonical():
    return _load_module(REPO_ROOT / "kg_pipeline" / "src" / "ontology.py", "ontology").CANONICAL_ENTITY_NAMES


def load_server_canonical():
    return _load_module(REPO_ROOT / "server" / "canonical.py", "canonical").CANONICAL_ENTITY_NAMES


class TestCanonicalSync:
    def test_same_keys(self):
        pipeline = load_pipeline_canonical()
        server = load_server_canonical()
        assert set(pipeline.keys()) == set(server.keys()), (
            f"Key mismatch.\n"
            f"Only in pipeline: {set(pipeline) - set(server)}\n"
            f"Only in server: {set(server) - set(pipeline)}"
        )

    def test_same_values(self):
        pipeline = load_pipeline_canonical()
        server = load_server_canonical()
        mismatches = {
            k: (pipeline[k], server[k])
            for k in set(pipeline) & set(server)
            if pipeline[k] != server[k]
        }
        assert not mismatches, f"Value mismatches: {mismatches}"

    def test_server_normalize_matches_pipeline_normalize(self):
        """normalize_entity_name in both modules should produce identical results."""
        pipeline_mod = _load_module(REPO_ROOT / "kg_pipeline" / "src" / "ontology.py", "ontology")
        server_mod = _load_module(REPO_ROOT / "server" / "canonical.py", "canonical")

        test_inputs = [
            "vitamin d", "Vitamin D3", "t2dm", "high blood pressure",
            "tirzepatide", "omega 3", "pre-diabetes", "Broccoli", "",
        ]
        for name in test_inputs:
            pipeline_result = pipeline_mod.normalize_entity_name(name)
            server_result = server_mod.normalize_entity_name(name)
            assert pipeline_result == server_result, (
                f"normalize_entity_name('{name}') differs: "
                f"pipeline='{pipeline_result}' vs server='{server_result}'"
            )

    def test_all_keys_are_lowercase(self):
        server = load_server_canonical()
        for k in server:
            assert k == k.lower(), f"server/canonical.py key '{k}' is not lowercase"
