#!/usr/bin/env python3
"""
improve_kg.py — 5-iteration KG improvement loop.

Each iteration:
  1. Gap analysis  → identify top missing-knowledge type
  2. Clean noise   → remove single-char/numeric garbage nodes from Neo4j
  3. Reextract     → rescue zero-triple papers with Claude Haiku (100/iter)
  4. Targeted fetch→ run smart_fetch with clusters chosen from gap analysis
  5. Broad sweep   → run full pipeline for new papers
  6. Entity resolve→ merge case/variant duplicate nodes
  7. Ingest + delta report

Usage:
    cd kg_pipeline && source venv/bin/activate
    python improve_kg.py            # 5 iterations (default)
    python improve_kg.py --iters 3  # custom iteration count
    python improve_kg.py --reextract-limit 50   # smaller reextract batch
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC  = ROOT / "src"
VENV_PYTHON = ROOT / "venv" / "bin" / "python"

sys.path.insert(0, str(SRC))


# ── Subprocess helper ─────────────────────────────────────────────────────────

def run(cmd: list[str], timeout: int = 1800, label: str = "") -> tuple[int, str]:
    if label:
        print(f"    → {label}")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def tail_output(out: str, n: int = 4) -> list[str]:
    return [l.strip() for l in out.splitlines() if l.strip()][-n:]


# ── Neo4j helpers ─────────────────────────────────────────────────────────────

def _driver():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from neo4j import GraphDatabase  # type: ignore
    uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER",     "foodnot4self")
    pw   = os.getenv("NEO4J_PASSWORD", "foodnot4self")
    return GraphDatabase.driver(uri, auth=(user, pw))


def kg_counts() -> dict:
    try:
        driver = _driver()
        with driver.session() as s:
            nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels  = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        driver.close()
        return {"nodes": nodes, "rels": rels}
    except Exception as e:
        return {"error": str(e)}


def clean_noise_nodes() -> dict:
    """
    Remove obviously-noisy nodes from Neo4j:
      - name length == 1 (single char: '1', 'A', 'C', etc.)
      - name is purely numeric ('12', '123')
      - name starts with '(' or '[' (malformed)
    Detaches and deletes the node and all its relationships.
    Returns {"deleted": N}.
    """
    try:
        driver = _driver()
        with driver.session() as s:
            result = s.run("""
                MATCH (n)
                WHERE n:Disease OR n:Food OR n:Nutrient OR n:Symptom
                   OR n:Drug OR n:LifestyleFactor OR n:Biomarker
                   OR n:Mechanism OR n:BiochemicalPathway
                WITH n
                WHERE size(n.name) <= 1
                   OR n.name =~ '^[0-9]+$'
                   OR n.name =~ '^[0-9][0-9]$'
                   OR n.name STARTS WITH '('
                   OR n.name STARTS WITH '['
                   OR n.name STARTS WITH '-'
                DETACH DELETE n
                RETURN count(*) AS deleted
            """).single()["deleted"]
        driver.close()
        return {"deleted": result}
    except Exception as e:
        return {"error": str(e)}


# ── Gap analysis ──────────────────────────────────────────────────────────────

def gap_analysis() -> dict:
    try:
        from kg_gap_analyzer import analyze_kg_gaps
        g = analyze_kg_gaps()
        return {
            "cond_no_food":    len(g.conditions_no_food_recs),
            "disease_no_bmk":  len(g.diseases_no_biomarker),
            "symptom_no_sig":  len(g.symptoms_no_early_signal),
            "nutrient_no_src": len(g.nutrients_no_food),
            "bmk_no_food":     len(g.biomarkers_no_food_link),
            "food_no_nutrient":len(g.foods_no_nutrients),
            "mech_no_food":    len(g.mechanisms_no_food),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Cluster rotation — each iteration targets the worst gap type ───────────────

# Maps gap key → smart_fetch clusters that address it
_GAP_CLUSTERS = {
    "symptom_no_sig":  "alzheimers,stroke,depression,hypertension,kidney_disease",
    "nutrient_no_src": "bone_health,bone_density,immune_health,cancer_prevention",
    "cond_no_food":    "diabetes,metabolic_syndrome,obesity,longevity,liver_disease",
    "disease_no_bmk":  "biomarker_nutrition,cardiovascular,pancreatic_cancer",
    "bmk_no_food":     "biomarker_nutrition,mechanism_pathways,clinical_trials_diet",
    "food_no_nutrient":"bone_density,immune_health,anti_inflammatory_diet",
    "mech_no_food":    "mechanism_pathways,gut_health,inflammation",
}


def choose_clusters(gaps: dict) -> str:
    """Pick the cluster set that best targets the largest gap."""
    if "error" in gaps:
        return "diabetes,cardiovascular,alzheimers,inflammation"
    # Rank gap types by count, pick top
    ranked = sorted(
        [(k, v) for k, v in gaps.items() if k in _GAP_CLUSTERS],
        key=lambda x: -x[1]
    )
    if ranked:
        top_key = ranked[0][0]
        print(f"    Top gap type: {top_key} ({ranked[0][1]} items) → using {_GAP_CLUSTERS[top_key]}")
        return _GAP_CLUSTERS[top_key]
    return "diabetes,cardiovascular,alzheimers"


# ── Single iteration ──────────────────────────────────────────────────────────

def run_iteration(n: int, total: int, reextract_limit: int) -> dict:
    bar = "═" * 60
    ts  = datetime.now().strftime("%H:%M:%S")
    print(f"\n{bar}")
    print(f"  ITERATION {n}/{total}  ·  {ts}")
    print(bar)

    before = kg_counts()
    if "error" not in before:
        print(f"  KG  : {before['nodes']:,} nodes  ·  {before['rels']:,} rels")

    # ── Step 1: Gap analysis ──────────────────────────────────────────────────
    print(f"\n  [1/6] Gap analysis…")
    gaps = gap_analysis()
    if "error" not in gaps:
        total_gaps = sum(gaps.values())
        top3 = sorted(gaps.items(), key=lambda x: -x[1])[:3]
        print(f"    {total_gaps:,} gap items — top: " +
              ", ".join(f"{k}={v}" for k, v in top3))
    clusters = choose_clusters(gaps)

    # ── Step 2: Clean noise nodes ─────────────────────────────────────────────
    print(f"\n  [2/6] Cleaning noise nodes…")
    cleaned = clean_noise_nodes()
    if "error" not in cleaned:
        print(f"    Deleted {cleaned['deleted']} noisy nodes (len≤1, numeric, malformed)")
    else:
        print(f"    Cleanup error: {cleaned['error']}")

    # ── Step 3: Reextract with Haiku ──────────────────────────────────────────
    print(f"\n  [3/6] Reextract {reextract_limit} zero-triple papers (Claude Haiku)…")
    code, out = run(
        [str(VENV_PYTHON), "src/reextract.py", "--limit", str(reextract_limit)],
        timeout=1800, label=f"reextract --limit {reextract_limit}",
    )
    improved = 0
    for line in out.splitlines():
        if line.startswith("Updated master_graph"):
            try:
                improved = int(line.split(":")[1].split("papers")[0].strip())
            except (IndexError, ValueError):
                pass
        if "No re-extraction candidates" in line:
            improved = 0
    print(f"    {improved} papers improved via Haiku re-extraction")

    # ── Step 4: Smart gap-targeted fetch ──────────────────────────────────────
    print(f"\n  [4/6] Smart gap fetch  (clusters: {clusters})…")
    code, out = run(
        [str(VENV_PYTHON), "src/smart_fetch.py", "--clusters", clusters],
        timeout=600, label=f"smart_fetch --clusters {clusters}",
    )
    for line in tail_output(out, 2):
        print(f"    {line}")

    # ── Step 5a: Europe PMC fetch (new data source) ───────────────────────────
    print(f"\n  [5a/6] Europe PMC fetch  (66 journals × 10 yr)…")
    code, out = run(
        [str(VENV_PYTHON), "src/fetch_europe_pmc.py"],
        timeout=600, label="fetch_europe_pmc.py",
    )
    epmc_new = 0
    for line in out.splitlines():
        import re
        m = re.search(r"\+(\d+)\s+new", line)
        if m:
            epmc_new = max(epmc_new, int(m.group(1)))
    for line in tail_output(out, 2):
        print(f"    {line}")

    # ── Step 5b: FDA drug labels fetch (new data source) ──────────────────────
    print(f"\n  [5b/6] FDA drug labels fetch  (food-drug interactions)…")
    code, out = run(
        [str(VENV_PYTHON), "src/fetch_fda_labels.py", "--max-labels", "200"],
        timeout=300, label="fetch_fda_labels.py",
    )
    fda_new = 0
    for line in out.splitlines():
        m = re.search(r"\+(\d+)\s+new", line)
        if m:
            fda_new = max(fda_new, int(m.group(1)))
    for line in tail_output(out, 1):
        print(f"    {line}")

    # ── Step 5c: Broad NCBI pipeline sweep ────────────────────────────────────
    print(f"\n  [5c/6] Broad NCBI sweep  (66 journals × 10 yr)…")
    code, out = run(
        [str(VENV_PYTHON), "run_pipeline.py"],
        timeout=1800, label="run_pipeline.py",
    )
    new_papers = epmc_new + fda_new
    new_triples = 0
    for line in out.splitlines():
        m = re.search(r"fetching\s+(\d+)\s+new", line, re.I)
        if m:
            new_papers += int(m.group(1))
        m = re.search(r"Consolidated\s+(\d+)\s+valid triples", line)
        if m:
            new_triples = int(m.group(1))
    print(f"    +{new_papers} new total  ·  {new_triples:,} valid triples now")

    # ── Step 6: Entity resolve + ingest ──────────────────────────────────────
    print(f"\n  [6/6] Entity resolution + ingest…")
    code, out = run(
        [str(VENV_PYTHON), "src/entity_resolver.py"],
        timeout=180, label="entity_resolver.py",
    )
    merged = 0
    for line in out.splitlines():
        if line.startswith("Merged:"):
            try:
                merged = int(line.split(":")[1].split("duplicate")[0].strip())
            except (IndexError, ValueError):
                pass
    print(f"    {merged} duplicate nodes merged")

    code, out = run(
        [str(VENV_PYTHON), "src/ingest_to_neo4j.py"],
        timeout=180, label="ingest_to_neo4j.py",
    )
    for line in tail_output(out, 1):
        print(f"    {line}")

    # ── Delta ─────────────────────────────────────────────────────────────────
    after = kg_counts()
    delta = {}
    if "error" not in after and "error" not in before:
        delta = {
            "nodes": after["nodes"] - before["nodes"],
            "rels":  after["rels"]  - before["rels"],
        }
        print(f"\n  Δ  +{delta['nodes']} nodes  +{delta['rels']} rels  →  "
              f"{after['nodes']:,} nodes  ·  {after['rels']:,} rels")

    return {
        "iter": n,
        "improved_papers": improved,
        "new_papers": new_papers,
        "merged_nodes": merged,
        "noise_deleted": cleaned.get("deleted", 0),
        "delta_nodes": delta.get("nodes", 0),
        "delta_rels":  delta.get("rels",  0),
        "total_nodes": after.get("nodes", 0),
        "total_rels":  after.get("rels", 0),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="5-iteration KG improvement loop")
    parser.add_argument("--iters",            type=int, default=5,  help="Number of iterations")
    parser.add_argument("--reextract-limit",  type=int, default=100, help="Papers per reextract pass")
    args = parser.parse_args()

    if not VENV_PYTHON.exists():
        print(f"ERROR: venv not found at {VENV_PYTHON}")
        sys.exit(1)

    start = datetime.now()
    print(f"[improve_kg] Starting {args.iters} iterations  ·  reextract_limit={args.reextract_limit}")
    print(f"[improve_kg] Venv: {VENV_PYTHON}")

    results = []
    for i in range(1, args.iters + 1):
        result = run_iteration(i, args.iters, args.reextract_limit)
        results.append(result)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = int((datetime.now() - start).total_seconds())
    print(f"\n{'═'*60}")
    print(f"  COMPLETE  ·  {args.iters} iterations  ·  {elapsed//60}m {elapsed%60}s")
    print(f"{'═'*60}")
    print(f"  {'Iter':<6} {'Reext':>6} {'NewPap':>7} {'Noise':>7} {'Merged':>7} {'ΔNodes':>7} {'ΔRels':>7}")
    print(f"  {'----':<6} {'------':>6} {'-------':>7} {'-------':>7} {'-------':>7} {'-------':>7} {'-------':>7}")
    for r in results:
        print(f"  {r['iter']:<6} {r['improved_papers']:>6} {r['new_papers']:>7} "
              f"{r['noise_deleted']:>7} {r['merged_nodes']:>7} "
              f"{r['delta_nodes']:>+7} {r['delta_rels']:>+7}")
    totals = {
        "improved": sum(r["improved_papers"] for r in results),
        "papers":   sum(r["new_papers"]      for r in results),
        "noise":    sum(r["noise_deleted"]   for r in results),
        "merged":   sum(r["merged_nodes"]    for r in results),
        "nodes":    sum(r["delta_nodes"]     for r in results),
        "rels":     sum(r["delta_rels"]      for r in results),
    }
    print(f"  {'TOTAL':<6} {totals['improved']:>6} {totals['papers']:>7} "
          f"{totals['noise']:>7} {totals['merged']:>7} "
          f"{totals['nodes']:>+7} {totals['rels']:>+7}")
    if results:
        last = results[-1]
        print(f"\n  Final KG: {last['total_nodes']:,} nodes  ·  {last['total_rels']:,} rels")


if __name__ == "__main__":
    sys.path.insert(0, str(SRC))
    main()
