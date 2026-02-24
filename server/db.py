"""
Shared SQLite database for pipeline history, KG stats trends, demand tracking,
contradiction records, fetch yield, and user snapshots.

Database file: data/health_map.db (relative to repo root).
All writes use WAL mode for concurrent readers.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, date
from pathlib import Path

_DB_PATH = Path(os.getenv(
    "HEALTH_MAP_DB",
    Path(__file__).resolve().parent.parent / "data" / "health_map.db",
))

_local = threading.local()


def _conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection (WAL mode, row factory)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(_DB_PATH.parent, exist_ok=True)
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables (idempotent)."""
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at    TEXT    NOT NULL,
            finished_at   TEXT,
            state         TEXT    DEFAULT 'running',
            new_papers    INTEGER DEFAULT 0,
            valid_triples INTEGER,
            total_triples INTEGER,
            elapsed_s     INTEGER,
            error         TEXT
        );

        CREATE TABLE IF NOT EXISTS kg_stats (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at           TEXT    NOT NULL,
            total_nodes           INTEGER,
            total_relationships   INTEGER,
            by_label              TEXT,
            by_relationship_type  TEXT
        );

        CREATE TABLE IF NOT EXISTS contradictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at     TEXT    NOT NULL,
            entity          TEXT    NOT NULL,
            disease         TEXT    NOT NULL,
            positive_rel    TEXT,
            pos_count       INTEGER DEFAULT 0,
            pos_strength    REAL,
            negative_rel    TEXT,
            neg_count       INTEGER DEFAULT 0,
            neg_strength    REAL,
            verdict         TEXT
        );

        CREATE TABLE IF NOT EXISTS query_demand (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT    NOT NULL,
            entity_name TEXT    NOT NULL,
            entity_type TEXT    NOT NULL,
            count       INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_demand_entity
            ON query_demand(entity_name, entity_type, recorded_at);

        CREATE TABLE IF NOT EXISTS fetch_yield (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            query_label            TEXT    NOT NULL,
            run_id                 TEXT,
            papers_returned        INTEGER DEFAULT 0,
            papers_new             INTEGER DEFAULT 0,
            triples_produced       INTEGER DEFAULT 0,
            avg_evidence_strength  REAL
        );

        CREATE TABLE IF NOT EXISTS context_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_token      TEXT    NOT NULL,
            recorded_at     TEXT    NOT NULL,
            age             INTEGER,
            conditions      TEXT,
            symptoms        TEXT,
            position_x      REAL,
            position_y      REAL,
            zone            TEXT,
            landmine_risks  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_token
            ON context_snapshots(user_token, recorded_at);
    """)
    c.commit()


# ── Pipeline runs ─────────────────────────────────────────────────────────────

def log_run_start() -> int:
    """Record the start of a pipeline run. Returns the run row id."""
    c = _conn()
    cur = c.execute(
        "INSERT INTO pipeline_runs (started_at, state) VALUES (?, 'running')",
        (datetime.now().isoformat(),),
    )
    c.commit()
    return cur.lastrowid


def log_run_end(
    run_id: int,
    *,
    new_papers: int = 0,
    valid_triples: int | None = None,
    total_triples: int | None = None,
    elapsed_s: int | None = None,
    error: str | None = None,
) -> None:
    """Update a pipeline run with its results."""
    state = "error" if error else "completed"
    c = _conn()
    c.execute(
        """UPDATE pipeline_runs
           SET finished_at = ?, state = ?, new_papers = ?,
               valid_triples = ?, total_triples = ?, elapsed_s = ?, error = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), state, new_papers,
         valid_triples, total_triples, elapsed_s, error, run_id),
    )
    c.commit()


def get_run_history(limit: int = 20) -> list[dict]:
    """Return recent pipeline runs, newest first."""
    c = _conn()
    rows = c.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── KG stats snapshots ───────────────────────────────────────────────────────

def save_kg_snapshot(
    total_nodes: int,
    total_relationships: int,
    by_label: dict | None = None,
    by_relationship_type: dict | None = None,
) -> None:
    """Save a KG stats snapshot (call once per stats request, at most daily)."""
    c = _conn()
    today = date.today().isoformat()
    existing = c.execute(
        "SELECT id FROM kg_stats WHERE recorded_at LIKE ?", (f"{today}%",)
    ).fetchone()
    if existing:
        return  # one snapshot per day
    c.execute(
        """INSERT INTO kg_stats (recorded_at, total_nodes, total_relationships,
                                  by_label, by_relationship_type)
           VALUES (?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), total_nodes, total_relationships,
         json.dumps(by_label or {}), json.dumps(by_relationship_type or {})),
    )
    c.commit()


def get_kg_trend(days: int = 30) -> list[dict]:
    """Return KG stats snapshots for the last N days."""
    c = _conn()
    rows = c.execute(
        """SELECT recorded_at, total_nodes, total_relationships,
                  by_label, by_relationship_type
           FROM kg_stats ORDER BY id DESC LIMIT ?""",
        (days,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["by_label"] = json.loads(d["by_label"]) if d["by_label"] else {}
        d["by_relationship_type"] = json.loads(d["by_relationship_type"]) if d["by_relationship_type"] else {}
        result.append(d)
    return result


# ── Contradictions ────────────────────────────────────────────────────────────

def save_contradiction(
    entity: str, disease: str,
    positive_rel: str, pos_count: int, pos_strength: float | None,
    negative_rel: str, neg_count: int, neg_strength: float | None,
    verdict: str,
) -> None:
    c = _conn()
    # Upsert: delete old record for same entity+disease, insert new
    c.execute(
        "DELETE FROM contradictions WHERE entity = ? AND disease = ?",
        (entity, disease),
    )
    c.execute(
        """INSERT INTO contradictions
           (detected_at, entity, disease, positive_rel, pos_count, pos_strength,
            negative_rel, neg_count, neg_strength, verdict)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), entity, disease,
         positive_rel, pos_count, pos_strength,
         negative_rel, neg_count, neg_strength, verdict),
    )
    c.commit()


def get_contradictions() -> list[dict]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM contradictions ORDER BY detected_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ── Query demand ──────────────────────────────────────────────────────────────

def log_demand(entities: list[str], entity_type: str) -> None:
    """Upsert demand counts for entities on today's date."""
    if not entities:
        return
    c = _conn()
    today = date.today().isoformat()
    for name in entities:
        name = name.strip()
        if not name:
            continue
        existing = c.execute(
            """SELECT id, count FROM query_demand
               WHERE entity_name = ? AND entity_type = ? AND recorded_at = ?""",
            (name, entity_type, today),
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE query_demand SET count = count + 1 WHERE id = ?",
                (existing["id"],),
            )
        else:
            c.execute(
                """INSERT INTO query_demand (recorded_at, entity_name, entity_type, count)
                   VALUES (?, ?, ?, 1)""",
                (today, name, entity_type),
            )
    c.commit()


def get_top_demand(limit: int = 20) -> list[dict]:
    """Return entities ranked by total demand count across all days."""
    c = _conn()
    rows = c.execute(
        """SELECT entity_name, entity_type, SUM(count) AS total
           FROM query_demand
           GROUP BY entity_name, entity_type
           ORDER BY total DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Fetch yield ───────────────────────────────────────────────────────────────

def log_yield(
    query_label: str,
    run_id: str | None = None,
    papers_returned: int = 0,
    papers_new: int = 0,
    triples_produced: int = 0,
    avg_evidence_strength: float | None = None,
) -> None:
    c = _conn()
    c.execute(
        """INSERT INTO fetch_yield
           (query_label, run_id, papers_returned, papers_new,
            triples_produced, avg_evidence_strength)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (query_label, run_id, papers_returned, papers_new,
         triples_produced, avg_evidence_strength),
    )
    c.commit()


def get_low_yield_queries(min_runs: int = 3, max_yield: float = 0.5) -> list[str]:
    """Return query labels that consistently produce < max_yield triples/paper."""
    c = _conn()
    rows = c.execute(
        """SELECT query_label,
                  COUNT(*) AS runs,
                  SUM(triples_produced) AS total_triples,
                  SUM(papers_new) AS total_papers
           FROM fetch_yield
           GROUP BY query_label
           HAVING runs >= ? AND total_papers > 0
                  AND CAST(total_triples AS REAL) / total_papers < ?""",
        (min_runs, max_yield),
    ).fetchall()
    return [r["query_label"] for r in rows]


def get_yield_stats() -> list[dict]:
    """Return per-query yield statistics."""
    c = _conn()
    rows = c.execute(
        """SELECT query_label,
                  COUNT(*) AS runs,
                  SUM(papers_returned) AS total_returned,
                  SUM(papers_new) AS total_new,
                  SUM(triples_produced) AS total_triples,
                  CASE WHEN SUM(papers_new) > 0
                       THEN ROUND(CAST(SUM(triples_produced) AS REAL) / SUM(papers_new), 2)
                       ELSE 0 END AS avg_triples_per_paper
           FROM fetch_yield
           GROUP BY query_label
           ORDER BY total_triples DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


# ── Context snapshots ─────────────────────────────────────────────────────────

def save_snapshot(
    user_token: str,
    age: int | None = None,
    conditions: list[str] | None = None,
    symptoms: list[str] | None = None,
    position_x: float | None = None,
    position_y: float | None = None,
    zone: str | None = None,
    landmine_risks: dict | None = None,
) -> int:
    """Save a context snapshot. Returns the snapshot id."""
    c = _conn()
    cur = c.execute(
        """INSERT INTO context_snapshots
           (user_token, recorded_at, age, conditions, symptoms,
            position_x, position_y, zone, landmine_risks)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_token, datetime.now().isoformat(), age,
         json.dumps(conditions or []), json.dumps(symptoms or []),
         position_x, position_y, zone,
         json.dumps(landmine_risks or {})),
    )
    c.commit()
    return cur.lastrowid


def get_trajectory(user_token: str, limit: int = 50) -> list[dict]:
    """Return snapshots for a user token, oldest first."""
    c = _conn()
    rows = c.execute(
        """SELECT recorded_at, age, conditions, symptoms,
                  position_x, position_y, zone, landmine_risks
           FROM context_snapshots
           WHERE user_token = ?
           ORDER BY id ASC
           LIMIT ?""",
        (user_token, limit),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["conditions"] = json.loads(d["conditions"]) if d["conditions"] else []
        d["symptoms"] = json.loads(d["symptoms"]) if d["symptoms"] else []
        d["landmine_risks"] = json.loads(d["landmine_risks"]) if d["landmine_risks"] else {}
        result.append(d)
    return result
