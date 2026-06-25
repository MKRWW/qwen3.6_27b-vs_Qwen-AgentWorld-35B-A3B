"""JSONL-Logging für Reproduzierbarkeit.

Jeder Run schreibt eine Datei results/raw/<track>_<model>_<regime>_<ts>.jsonl:
  Zeile 1 = run_header (Modell, Endpoint, Sampling, git-SHA, Zeit)
  Zeile N = ein API-Call ODER ein Task/Triple-Ergebnis.
Raw-Logs sind gitignored; nur aggregierte Summaries werden committet.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

HARNESS_VERSION = "0.1.0"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "results", "raw")


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(__file__), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Recorder:
    def __init__(self, track: int, model_key: str, model_id: str, endpoint: str,
                 regime: str, sampling: dict, ts: str | None = None):
        os.makedirs(RAW_DIR, exist_ok=True)
        ts = ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fname = f"track{track}_{model_key}_{regime}_{ts}.jsonl"
        self.path = os.path.join(RAW_DIR, fname)
        self._f = open(self.path, "a", encoding="utf-8")
        self._write({
            "type": "run_header", "track": track, "model": model_key,
            "model_id": model_id, "endpoint": endpoint, "regime": regime,
            "sampling": sampling, "repo_git_sha": _git_sha(),
            "started_at_utc": _now_iso(), "harness_version": HARNESS_VERSION,
        })

    def _write(self, obj: dict):
        self._f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._f.flush()

    def log_call(self, **kw):
        self._write({"type": "api_call", "logged_at_utc": _now_iso(), **kw})

    def log_result(self, **kw):
        """Ein Task- (Track 1) oder Triple-Ergebnis (Track 2) inkl. Scores."""
        self._write({"type": "result", "logged_at_utc": _now_iso(), **kw})

    def close(self):
        self._write({"type": "run_footer", "ended_at_utc": _now_iso()})
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
