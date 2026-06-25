"""Track 1 — Hype-Test (Policy / Agent über hermes).

hermes (WSL, v0.17.0) wird je Task auf Backend A bzw. B gezeigt und in einer
frischen Sandbox-Kopie der Task ausgeführt. Danach läuft das Task-Oracle.

Adapter-Punkt: `run_hermes_task()` kapselt den exakten hermes-CLI-Aufruf. Die
Flags hängen von der hermes-Version ab — hier zentral anpassen, sobald via
`hermes --help` verifiziert (TODO unten).

Aufruf:
  python harness/run_track1_policy.py --models A,B --regime greedy --tasks tasks/
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
import client as C          # noqa: E402
from record import Recorder  # noqa: E402


def load_tasks(tasks_dir: str) -> list[dict]:
    tasks = []
    for spec in sorted(glob.glob(os.path.join(tasks_dir, "*", "tasks", "*", "task.json"))):
        with open(spec, encoding="utf-8") as f:
            t = json.load(f)
        t["_dir"] = os.path.dirname(spec)
        t["_id"] = os.path.relpath(t["_dir"], tasks_dir)
        tasks.append(t)
    return tasks


def to_wsl_path(win_path: str) -> str:
    """C:\\Users\\x -> /mnt/c/Users/x (für hermes in WSL)."""
    p = os.path.abspath(win_path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        return f"/mnt/{p[0].lower()}{p[2:]}"
    return p


def run_hermes_task(task: dict, model: C.ModelSpec, sandbox: str, timeout: int = 600) -> dict:
    """hermes nicht-interaktiv auf `task` in `sandbox` laufen lassen.

    TODO(verifizieren): exakte hermes-Flags via `wsl hermes --help` bestätigen.
    Annahme (anpassen): hermes liest OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL
    aus der Umgebung und akzeptiert `hermes run -p "<prompt>" --cwd <dir> --headless`.
    """
    env = (
        f"export OPENAI_BASE_URL='{model.endpoint}'; "
        f"export OPENAI_API_KEY='{model.api_key}'; "
        f"export OPENAI_MODEL='{model.model_id}'; "
    )
    wsl_dir = to_wsl_path(sandbox)
    prompt = task["prompt"].replace("'", "'\\''")
    cmd = (
        f"{env} cd '{wsl_dir}' && "
        f"hermes run -p '{prompt}' --headless 2>&1"   # TODO: Flags verifizieren
    )
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["wsl.exe", "-e", "bash", "-lc", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        transcript = proc.stdout
        rc = proc.returncode
        crash = None
    except subprocess.TimeoutExpired as e:
        transcript = (e.stdout or "") if isinstance(e.stdout, str) else ""
        rc = -1
        crash = "timeout"
    return {"transcript": transcript, "returncode": rc, "crash": crash,
            "wall_clock_s": round(time.monotonic() - t0, 2)}


def run_oracle(task: dict, sandbox: str) -> dict:
    """Task-Oracle in der Sandbox. Default: `oracle.sh` ausführen, exit 0 = success.
    SWE-Tasks nutzen typischerweise pytest darin."""
    oracle = os.path.join(task["_dir"], "oracle.sh")
    if not os.path.exists(oracle):
        return {"success": None, "note": "kein oracle.sh"}
    wsl_dir = to_wsl_path(sandbox)
    wsl_oracle = to_wsl_path(oracle)
    cmd = f"cd '{wsl_dir}' && bash '{wsl_oracle}' 2>&1"
    proc = subprocess.run(["wsl.exe", "-e", "bash", "-lc", cmd],
                          capture_output=True, text=True, timeout=300)
    return {"success": proc.returncode == 0, "oracle_output": proc.stdout[-2000:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="A,B")
    ap.add_argument("--regime", default="greedy")
    ap.add_argument("--tasks", default="tasks/")
    args = ap.parse_args()

    cfg = C.load_config()
    regime = C.get_regime(args.regime, cfg)
    tasks = load_tasks(args.tasks)
    print(f"{len(tasks)} Tasks geladen.")

    for model_key in args.models.split(","):
        model = C.get_model(model_key, cfg)
        rec = Recorder(track=1, model_key=model_key, model_id=model.model_id,
                       endpoint=model.endpoint, regime=regime.name, sampling=regime.params)
        with rec:
            for t in tasks:
                with tempfile.TemporaryDirectory(prefix="t1_") as sandbox:
                    src = os.path.join(t["_dir"], "workspace")
                    if os.path.isdir(src):
                        shutil.copytree(src, sandbox, dirs_exist_ok=True)
                    run = run_hermes_task(t, model, sandbox)
                    oracle = run_oracle(t, sandbox)
                    rec.log_result(task_id=t["_id"], domain=t.get("domain"),
                                   run=run, oracle=oracle)
                    print(f"  [{model_key}] {t['_id']}: success={oracle.get('success')} "
                          f"crash={run['crash']} {run['wall_clock_s']}s")
        print(f"  -> {rec.path}")


if __name__ == "__main__":
    main()
