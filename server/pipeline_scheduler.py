"""
Adaptive pipeline scheduler — runs smart-fetch → extract → ingest automatically.

Strategy:
  - Runs in a background thread; checks every minute whether it's time.
  - Adaptive interval: productive runs (many new papers) → schedule sooner;
    empty runs → back off exponentially up to MAX_INTERVAL.
  - "Busy" detection: skips a scheduled run if one is already in progress.
  - Manual trigger: force an immediate run via trigger_now().

Interval ladder:
  >10 new papers  → 30 min   (hot — keep filling)
  1–10 papers     → 60 min   (warm)
  0 papers        → 2× current, max 6 h  (saturated, back off)
  Error           → 30 min   (retry quickly)
"""
from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
_MIN_INTERVAL  = 60          # 1 minute — fire again as soon as previous run finishes
_BASE_INTERVAL = 60          # start at 1 minute
_MAX_INTERVAL  = 30 * 60     # back off to 30 min max when corpus is saturated
_CHECK_EVERY   = 10          # poll every 10 seconds for faster response

_KG_PIPELINE_DIR = Path(
    os.getenv("KG_PIPELINE_DIR", Path(__file__).resolve().parent.parent / "kg_pipeline")
)
_VENV_PYTHON = _KG_PIPELINE_DIR / "venv" / "bin" / "python"


class PipelineScheduler:
    """Thread-safe adaptive pipeline scheduler."""

    def __init__(self):
        self.state: str = "idle"          # idle | running
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.interval: int = _BASE_INTERVAL
        self.last_result: dict = {}
        self.history: list[dict] = []     # last 10 run summaries

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ── Internal pipeline execution ───────────────────────────────────────────

    def _run(self, cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
        """Run a subprocess, return (returncode, combined output)."""
        try:
            result = subprocess.run(
                cmd, cwd=str(cwd),
                capture_output=True, text=True, timeout=timeout,
            )
            return result.returncode, (result.stdout + result.stderr).strip()
        except subprocess.TimeoutExpired:
            return -1, "timeout"
        except Exception as e:
            return -1, str(e)

    def _run_pipeline(self) -> dict:
        """Execute smart-fetch → extract → ingest. Returns run summary."""
        started = datetime.now()
        summary: dict = {"started": started.isoformat(), "steps": {}}

        if not _VENV_PYTHON.exists():
            summary["error"] = f"venv not found at {_VENV_PYTHON}"
            return summary

        # Step 1: smart-fetch
        code, out = self._run(
            [str(_VENV_PYTHON), "src/smart_fetch.py"],
            _KG_PIPELINE_DIR, timeout=300,
        )
        summary["steps"]["smart_fetch"] = {"code": code, "output": out[-800:]}

        # Parse new paper count from output
        new_papers = 0
        for line in out.splitlines():
            if "Smart fetch complete:" in line:
                try:
                    new_papers = int(line.split(":")[1].split("new")[0].strip())
                except (IndexError, ValueError):
                    pass
        summary["new_papers"] = new_papers

        if code != 0 or new_papers == 0:
            summary["skipped_extract"] = True
            summary["elapsed_s"] = int((datetime.now() - started).total_seconds())
            return summary

        # Step 2: extract
        code, out = self._run(
            [str(_VENV_PYTHON), "src/extract_triples.py"],
            _KG_PIPELINE_DIR, timeout=1200,
        )
        summary["steps"]["extract"] = {"code": code, "output": out[-800:]}

        # Parse triple count
        for line in out.splitlines():
            if "valid relationships" in line:
                try:
                    summary["valid_triples"] = int(line.split("extracted")[1].split("valid")[0].strip())
                except (IndexError, ValueError):
                    pass

        # Step 3: ingest
        code, out = self._run(
            [str(_VENV_PYTHON), "src/ingest_to_neo4j.py"],
            _KG_PIPELINE_DIR, timeout=120,
        )
        summary["steps"]["ingest"] = {"code": code, "output": out[-400:]}
        summary["elapsed_s"] = int((datetime.now() - started).total_seconds())
        return summary

    # ── Scheduler loop ────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.wait(_CHECK_EVERY):
            with self._lock:
                if self.state == "running":
                    continue
                if self.next_run is None or datetime.now() < self.next_run:
                    continue
                self.state = "running"

            try:
                result = self._run_pipeline()
            except Exception as e:
                result = {"error": str(e), "new_papers": 0}

            with self._lock:
                self.last_run = datetime.now()
                self.last_result = result
                self.history = ([result] + self.history)[:10]

                new_papers = result.get("new_papers", 0)
                if result.get("error"):
                    self.interval = _MIN_INTERVAL              # retry immediately on error
                elif new_papers > 0:
                    self.interval = _MIN_INTERVAL              # found papers — keep firing
                else:
                    self.interval = min(self.interval * 2, _MAX_INTERVAL)  # saturated — back off

                self.next_run = datetime.now() + timedelta(seconds=self.interval)
                self.state = "idle"

                print(
                    f"[Scheduler] Run complete — {new_papers} new papers. "
                    f"Next run in {self.interval // 60} min "
                    f"({self.next_run.strftime('%H:%M')})"
                )

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, initial_delay_minutes: int = 5):
        """Start the background scheduler thread."""
        with self._lock:
            self.next_run = datetime.now() + timedelta(minutes=initial_delay_minutes)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pipeline-scheduler")
        self._thread.start()
        print(f"[Scheduler] Started — first run in {initial_delay_minutes} min")

    def stop(self):
        self._stop.set()

    def trigger_now(self):
        """Force an immediate run (bypasses cooldown)."""
        with self._lock:
            if self.state == "running":
                return {"status": "already_running"}
            self.next_run = datetime.now()
        return {"status": "triggered"}

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "last_run": self.last_run.isoformat() if self.last_run else None,
                "next_run": self.next_run.isoformat() if self.next_run else None,
                "next_run_in_minutes": (
                    max(0, int((self.next_run - datetime.now()).total_seconds() // 60))
                    if self.next_run else None
                ),
                "interval_minutes": self.interval // 60,
                "last_new_papers": self.last_result.get("new_papers"),
                "last_valid_triples": self.last_result.get("valid_triples"),
                "last_elapsed_s": self.last_result.get("elapsed_s"),
                "runs_completed": len(self.history),
                "kg_pipeline_dir": str(_KG_PIPELINE_DIR),
                "venv_found": _VENV_PYTHON.exists(),
            }


# ── Singleton ──────────────────────────────────────────────────────────────────
scheduler = PipelineScheduler()
