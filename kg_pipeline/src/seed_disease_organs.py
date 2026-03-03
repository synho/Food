"""
Seed Disease → OCCURS_AT → BodySystem relationships into Neo4j.

Maps every known disease to its primary organ(s)/body system(s) so the KG
is navigable by anatomy. Uses MERGE to be idempotent — safe to re-run.

Usage:
    python src/seed_disease_organs.py              # seed into Neo4j
    python src/seed_disease_organs.py --dry-run    # print mappings only
"""
import argparse
import os
import sys
from pathlib import Path

# Allow running from kg_pipeline/ or kg_pipeline/src/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ontology import normalize_entity_name

# ── Disease → Organ/Body System mappings ────────────────────────────────────
# Each disease maps to a list of (organ_canonical_name, context_description).
# The context describes WHY this disease is located in that organ.

DISEASE_ORGAN_MAP: dict[str, list[tuple[str, str]]] = {
    # ── Cancer ───────────────────────────────────────────────────────────────
    "Breast cancer": [
        ("Breast", "Breast cancer originates in the mammary gland tissue"),
    ],
    "Colorectal cancer": [
        ("Large intestine", "Colorectal cancer develops in the colon or rectum"),
        ("Gastrointestinal tract", "Colorectal cancer is a GI tract malignancy"),
    ],
    "Lung cancer": [
        ("Lungs", "Lung cancer arises in the pulmonary epithelium"),
        ("Respiratory system", "Lung cancer is a respiratory system malignancy"),
    ],
    "Prostate cancer": [
        ("Prostate", "Prostate cancer develops in the prostate gland"),
    ],
    "Gastric cancer": [
        ("Stomach", "Gastric cancer originates in the stomach lining"),
        ("Gastrointestinal tract", "Gastric cancer is a GI tract malignancy"),
    ],
    "Esophageal cancer": [
        ("Esophagus", "Esophageal cancer develops in the esophageal mucosa"),
        ("Gastrointestinal tract", "Esophageal cancer is a GI tract malignancy"),
    ],
    "Ovarian cancer": [
        ("Ovaries", "Ovarian cancer originates in the ovarian tissue"),
    ],
    "Cervical cancer": [
        ("Cervix", "Cervical cancer develops in the cervix"),
        ("Uterus", "The cervix is part of the uterus"),
    ],
    "Endometrial cancer": [
        ("Uterus", "Endometrial cancer develops in the uterine lining"),
    ],
    "Bladder cancer": [
        ("Bladder", "Bladder cancer arises in the urinary bladder lining"),
    ],
    "Kidney cancer": [
        ("Kidneys", "Kidney cancer (renal cell carcinoma) originates in the kidneys"),
    ],
    "Liver cancer": [
        ("Liver", "Hepatocellular carcinoma originates in liver hepatocytes"),
    ],
    "Pancreatic cancer": [
        ("Pancreas", "Pancreatic cancer develops in the pancreatic tissue"),
    ],
    "Melanoma": [
        ("Skin", "Melanoma originates in the melanocytes of the skin"),
    ],
    "Glioblastoma": [
        ("Brain", "Glioblastoma is a primary brain tumor arising from glial cells"),
    ],
    "Thyroid cancer": [
        ("Thyroid gland", "Thyroid cancer develops in the thyroid gland"),
    ],
    "Leukemia": [
        ("Blood", "Leukemia is a cancer of blood-forming tissues"),
    ],
    "Lymphoma": [
        ("Immune system", "Lymphoma is a cancer of the lymphatic/immune system"),
    ],

    # ── Autoimmune ───────────────────────────────────────────────────────────
    "Rheumatoid arthritis": [
        ("Joints", "Rheumatoid arthritis primarily attacks synovial joints"),
        ("Immune system", "Rheumatoid arthritis is an autoimmune disorder"),
    ],
    "Systemic lupus erythematosus": [
        ("Immune system", "SLE is a systemic autoimmune disease"),
        ("Skin", "SLE commonly manifests with skin rashes"),
        ("Kidneys", "Lupus nephritis is a major complication of SLE"),
    ],
    "Multiple sclerosis": [
        ("Brain", "MS causes demyelination in the brain"),
        ("Spinal cord", "MS affects the spinal cord white matter"),
        ("Nervous system", "MS is a disease of the central nervous system"),
        ("Immune system", "MS is autoimmune-mediated"),
    ],
    "Type 1 diabetes": [
        ("Pancreas", "Type 1 diabetes destroys insulin-producing beta cells in the pancreas"),
        ("Immune system", "Type 1 diabetes is autoimmune-mediated"),
    ],
    "Psoriasis": [
        ("Skin", "Psoriasis manifests as skin plaques"),
        ("Immune system", "Psoriasis is immune-mediated"),
    ],
    "Psoriatic arthritis": [
        ("Joints", "Psoriatic arthritis affects peripheral joints"),
        ("Skin", "Associated with psoriasis skin manifestations"),
    ],
    "Crohn's disease": [
        ("Gastrointestinal tract", "Crohn's can affect any part of the GI tract"),
        ("Small intestine", "Crohn's most commonly affects the terminal ileum"),
        ("Immune system", "Crohn's disease involves immune dysregulation"),
    ],
    "Ulcerative colitis": [
        ("Large intestine", "Ulcerative colitis is confined to the colon and rectum"),
        ("Gastrointestinal tract", "UC is an inflammatory bowel disease"),
    ],
    "Celiac disease": [
        ("Small intestine", "Celiac disease damages the small intestinal villi"),
        ("Immune system", "Celiac disease is an autoimmune reaction to gluten"),
    ],

    # ── GI / Digestive ──────────────────────────────────────────────────────
    "Irritable bowel syndrome": [
        ("Gastrointestinal tract", "IBS is a functional GI disorder"),
        ("Large intestine", "IBS symptoms are predominantly colonic"),
    ],
    "Gastroesophageal reflux disease": [
        ("Esophagus", "GERD causes acid damage to the esophageal mucosa"),
        ("Stomach", "GERD involves gastric acid reflux"),
    ],
    "Peptic ulcer": [
        ("Stomach", "Peptic ulcers develop in the stomach lining"),
        ("Gastrointestinal tract", "Peptic ulcers are a GI condition"),
    ],
    "Functional dyspepsia": [
        ("Stomach", "Functional dyspepsia affects gastric function"),
    ],
    "Non-alcoholic fatty liver disease": [
        ("Liver", "NAFLD causes fat accumulation in liver hepatocytes"),
    ],

    # ── Mental Health ────────────────────────────────────────────────────────
    "Major depressive disorder": [
        ("Brain", "Depression involves dysregulation of brain neurotransmitter systems"),
    ],
    "Anxiety disorder": [
        ("Brain", "Anxiety disorders involve amygdala and prefrontal cortex dysfunction"),
    ],
    "Bipolar disorder": [
        ("Brain", "Bipolar disorder involves brain mood-regulation circuits"),
    ],
    "PTSD": [
        ("Brain", "PTSD involves hippocampal and amygdala changes"),
    ],
    "Schizophrenia": [
        ("Brain", "Schizophrenia involves dopaminergic dysregulation in the brain"),
    ],
    "Eating disorder": [
        ("Brain", "Eating disorders involve brain reward and appetite circuits"),
        ("Gastrointestinal tract", "Eating disorders have GI consequences"),
    ],

    # ── Respiratory ──────────────────────────────────────────────────────────
    "COPD": [
        ("Lungs", "COPD causes irreversible airway obstruction in the lungs"),
        ("Respiratory system", "COPD is a chronic respiratory disease"),
    ],
    "Asthma": [
        ("Lungs", "Asthma causes reversible bronchoconstriction in the lungs"),
        ("Respiratory system", "Asthma is a chronic respiratory condition"),
        ("Immune system", "Asthma involves immune hypersensitivity"),
    ],
    "Pulmonary fibrosis": [
        ("Lungs", "Pulmonary fibrosis causes lung tissue scarring"),
    ],

    # ── Musculoskeletal ──────────────────────────────────────────────────────
    "Osteoarthritis": [
        ("Joints", "Osteoarthritis degrades articular cartilage in joints"),
    ],
    "Gout": [
        ("Joints", "Gout causes urate crystal deposition in joints"),
    ],
    "Back pain": [
        ("Spinal cord", "Back pain commonly involves the spinal structures"),
        ("Bones", "Back pain can involve vertebral bone pathology"),
    ],
    "Osteoporosis": [
        ("Bones", "Osteoporosis reduces bone mineral density"),
    ],
    "Sarcopenia": [
        ("Skeletal muscle", "Sarcopenia is age-related loss of skeletal muscle mass"),
    ],

    # ── Eye Diseases ─────────────────────────────────────────────────────────
    "Macular degeneration": [
        ("Eyes", "AMD affects the macula of the retina"),
    ],
    "Glaucoma": [
        ("Eyes", "Glaucoma damages the optic nerve in the eye"),
    ],
    "Diabetic retinopathy": [
        ("Eyes", "Diabetic retinopathy damages retinal blood vessels"),
    ],
    "Cataracts": [
        ("Eyes", "Cataracts cloud the lens of the eye"),
    ],

    # ── Common Chronic ───────────────────────────────────────────────────────
    "Anemia": [
        ("Blood", "Anemia is a deficiency in blood hemoglobin or red blood cells"),
    ],
    "Iron-deficiency anaemia": [
        ("Blood", "Iron-deficiency anaemia reduces blood hemoglobin production"),
    ],
    "Migraine": [
        ("Brain", "Migraine involves neurovascular mechanisms in the brain"),
    ],
    "Hypothyroidism": [
        ("Thyroid gland", "Hypothyroidism is underactive thyroid hormone production"),
    ],
    "Hyperthyroidism": [
        ("Thyroid gland", "Hyperthyroidism is overactive thyroid hormone production"),
    ],
    "Insomnia": [
        ("Brain", "Insomnia involves brain sleep-wake cycle dysregulation"),
    ],

    # ── Existing KG diseases ────────────────────────────────────────────────
    "Alzheimer's disease": [
        ("Brain", "Alzheimer's causes neurodegeneration in the cerebral cortex and hippocampus"),
    ],
    "Dementia": [
        ("Brain", "Dementia involves progressive brain neurodegeneration"),
    ],
    "Stroke": [
        ("Brain", "Stroke causes ischemic or hemorrhagic brain damage"),
        ("Cardiovascular system", "Stroke is a cerebrovascular event"),
    ],
    "Cardiovascular disease": [
        ("Heart", "CVD includes coronary artery disease affecting the heart"),
        ("Cardiovascular system", "CVD encompasses diseases of blood vessels and heart"),
    ],
    "Hypertension": [
        ("Cardiovascular system", "Hypertension is sustained high arterial blood pressure"),
        ("Heart", "Hypertension increases cardiac workload"),
        ("Kidneys", "Hypertension damages renal vasculature"),
    ],
    "Type 2 diabetes": [
        ("Pancreas", "T2DM involves pancreatic beta-cell dysfunction"),
        ("Cardiovascular system", "T2DM significantly increases cardiovascular risk"),
    ],
    "Prediabetes": [
        ("Pancreas", "Prediabetes reflects early pancreatic beta-cell impairment"),
    ],
    "Chronic kidney disease": [
        ("Kidneys", "CKD is progressive loss of kidney function"),
    ],
    "Obesity": [
        ("Cardiovascular system", "Obesity increases cardiovascular disease risk"),
    ],
    "Chronic inflammation": [
        ("Immune system", "Chronic inflammation is sustained immune activation"),
    ],
}


def seed_disease_organs(dry_run: bool = False) -> dict:
    """Create Disease -[OCCURS_AT]-> BodySystem relationships in Neo4j."""
    total_mappings = sum(len(organs) for organs in DISEASE_ORGAN_MAP.values())
    print(f"Disease-organ seed: {len(DISEASE_ORGAN_MAP)} diseases → {total_mappings} relationships")

    if dry_run:
        for disease, organs in sorted(DISEASE_ORGAN_MAP.items()):
            organ_names = ", ".join(o[0] for o in organs)
            print(f"  {disease} → {organ_names}")
        print(f"\n[DRY RUN] {total_mappings} relationships planned. No Neo4j writes.")
        return {"dry_run": True, "diseases": len(DISEASE_ORGAN_MAP), "relationships": total_mappings}

    from neo4j import GraphDatabase

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "foodnot4self")
    neo4j_pw = os.getenv("NEO4J_PASSWORD", "foodnot4self")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pw))
    created = 0
    merged = 0

    with driver.session() as session:
        for disease_name, organs in DISEASE_ORGAN_MAP.items():
            # Normalize disease name through ontology
            disease_canonical = normalize_entity_name(disease_name)
            disease_key = disease_canonical.lower()

            for organ_name, context in organs:
                organ_canonical = normalize_entity_name(organ_name)
                organ_key = organ_canonical.lower()

                result = session.run("""
                    MERGE (d:Disease {name: $disease_key})
                    SET d.display_name = $disease_display
                    MERGE (b:BodySystem {name: $organ_key})
                    SET b.display_name = $organ_display
                    MERGE (d)-[r:OCCURS_AT {source_id: 'ontology_seed'}]->(b)
                    ON CREATE SET r.context = $context,
                                  r.source_type = 'ontology_seed',
                                  r.journal = 'Medical ontology',
                                  r.pub_date = '2025-01-01',
                                  r.seeded = true
                    RETURN type(r) AS rel_type,
                           CASE WHEN r.context = $context THEN 'existing' ELSE 'created' END AS status
                """, {
                    "disease_key": disease_key,
                    "disease_display": disease_canonical,
                    "organ_key": organ_key,
                    "organ_display": organ_canonical,
                    "context": context,
                })
                record = result.single()
                if record:
                    if record["status"] == "created":
                        merged += 1
                    else:
                        created += 1

                total = created + merged
                if total % 20 == 0 and total > 0:
                    print(f"  Progress: {total}/{total_mappings} relationships processed")

    driver.close()
    total = created + merged
    print(f"\nSeed complete: {total} relationships processed "
          f"({created} new, {merged} already existed)")
    return {"diseases": len(DISEASE_ORGAN_MAP), "relationships_total": total,
            "new": created, "existing": merged}


def main():
    parser = argparse.ArgumentParser(description="Seed disease→organ relationships into Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Print mappings without writing to Neo4j")
    args = parser.parse_args()
    seed_disease_organs(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
