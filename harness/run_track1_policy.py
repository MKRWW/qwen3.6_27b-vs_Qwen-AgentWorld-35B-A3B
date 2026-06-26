"""Track 1 — Hype-Test (Policy / Agent ueber hermes).

hermes (WSL) wird je Modell in einem ISOLIERTEN, nicht-invasiven Bench-Home
gefahren (eigenes config.yaml; die echte ~/.hermes-Config bleibt unangetastet)
und je Task in einer frischen WSL-Sandbox auf den Buggy-Workspace losgelassen.
Danach entscheidet das Task-Oracle (pytest in einer dedizierten Bench-venv).

Die hermes-Invocation-Recipe (hart erarbeitet, siehe docs/HERMES_SETUP.md):
  HERMES_HOME=<bench>  OPENAI_API_KEY=<key>  HERMES_INFERENCE_MODEL=<model_id>
  hermes -z "<prompt>" --yolo --cli      (cwd = Sandbox)
mit config.yaml: provider custom, base_url, api_key, context_length=64000,
max_tokens=2048 (B serviert nur 32k < hermes-Floor 64k -> Override + Output-Cap).

Aufruf:
  python harness/run_track1_policy.py --models A,B --regime greedy --tasks tasks/
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import client as C          # noqa: E402
from record import Recorder  # noqa: E402

REPO_WIN = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BENCH_VENV = "$HOME/.cache/awbench-venv"


def wsl(script: str, *, input_text: str | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(["wsl.exe", "-e", "bash", "-lc", script],
                          capture_output=True, text=True, input=input_text, timeout=timeout)


def to_wsl_path(win_path: str) -> str:
    p = os.path.abspath(win_path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        return f"/mnt/{p[0].lower()}{p[2:]}"
    return p


REPO_WSL = to_wsl_path(REPO_WIN)


def ensure_bench_venv():
    """Dedizierte venv mit pytest fuer die Oracles (entkoppelt vom System-Python)."""
    wsl(f'V={BENCH_VENV}; [ -x "$V/bin/pytest" ] || (python3 -m venv "$V" && '
        f'"$V/bin/pip" -q install pytest >/dev/null 2>&1)', timeout=300)


def write_bench_home(model: C.ModelSpec, hcfg: dict) -> str:
    """Isoliertes HERMES_HOME mit config.yaml fuer dieses Modell anlegen."""
    home = f"/tmp/hermes-bench-{model.key}"
    cfg_yaml = (
        "model:\n"
        f'  default: "{model.model_id}"\n'
        "  provider: custom\n"
        f"  base_url: {model.endpoint}\n"
        f'  api_key: "{model.api_key}"\n'
        f"  context_length: {hcfg['context_length']}\n"
        f"  max_tokens: {hcfg['max_tokens']}\n"
        "toolsets:\n"
        f"- {hcfg['toolset']}\n"
        "agent:\n"
        f"  max_turns: {hcfg['max_turns']}\n"
        "auxiliary:\n"
        "  compression:\n"
        f"    context_length: {hcfg['context_length']}\n"
    )
    wsl(f'mkdir -p "{home}" && cat > "{home}/config.yaml"', input_text=cfg_yaml)
    return home


def load_tasks(tasks_dir: str) -> list[dict]:
    tasks = []
    for spec in sorted(glob.glob(os.path.join(tasks_dir, "*", "tasks", "*", "task.json"))):
        with open(spec, encoding="utf-8") as f:
            t = json.load(f)
        t["_dir_win"] = os.path.dirname(spec)
        t["_dir_wsl"] = to_wsl_path(os.path.dirname(spec))
        t["_id"] = os.path.relpath(os.path.dirname(spec), tasks_dir).replace("\\", "/")
        tasks.append(t)
    return tasks


def run_task(model: C.ModelSpec, home: str, task: dict, timeout: int = 400) -> dict:
    """Eine Sandbox, hermes drauf, dann Oracle. Gibt Mess-Dict zurueck."""
    prompt = task["prompt"].replace('"', '\\"')
    tdir = task["_dir_wsl"]
    # Komplett-Skript: sandbox, copy, hermes, oracle, diff, cleanup — atomar in WSL.
    # Textfelder werden base64-kodiert ausgegeben (newline-/quote-sicher), Parsing
    # passiert in Python (kein fragiles eingebettetes Heredoc).
    script = f'''
set -uo pipefail
V={BENCH_VENV}
SB=$(mktemp -d)
cp -r "{tdir}/workspace/." "$SB/" 2>/dev/null; rm -rf "$SB/__pycache__"
ORACLE_BEFORE=$(cd "$SB" && "$V/bin/pytest" -q 2>&1 | tail -1)
cd "$SB"
T0=$(date +%s)
HERMES_HOME="{home}" OPENAI_API_KEY="{model.api_key}" HERMES_INFERENCE_MODEL="{model.model_id}" \
  timeout {timeout} hermes -z "{prompt}" --yolo --cli > /tmp/hermes_out.$$ 2>&1
HEXIT=$?
WALL=$(($(date +%s)-T0))
TRANSCRIPT=$(tail -c 2000 /tmp/hermes_out.$$; rm -f /tmp/hermes_out.$$)
cd "$SB" && "$V/bin/pytest" -q > /tmp/oracle.$$ 2>&1
OEXIT=$?
ORACLE_AFTER=$(tail -3 /tmp/oracle.$$; rm -f /tmp/oracle.$$)
DIFF=$(diff -r --exclude=__pycache__ --exclude=.git "{tdir}/workspace" "$SB" 2>/dev/null | head -60 || true)
rm -rf "$SB"
b64() {{ echo -n "$1" | base64 -w0; }}
echo "__RESULT__$HEXIT|$OEXIT|$WALL|$(b64 "$ORACLE_BEFORE")|$(b64 "$ORACLE_AFTER")|$(b64 "$TRANSCRIPT")|$(b64 "$DIFF")"
'''
    proc = wsl(script, timeout=timeout + 120)
    import base64
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT__"):
            try:
                hexit, oexit, wall, b, a, tr, df = line[len("__RESULT__"):].split("|")
                dec = lambda s: base64.b64decode(s).decode("utf-8", "replace") if s else ""
                return {
                    "hermes_exit": int(hexit), "oracle_pass": int(oexit) == 0,
                    "wall_clock_s": int(wall),
                    "oracle_before": dec(b), "oracle_after": dec(a),
                    "transcript_tail": dec(tr), "diff": dec(df),
                }
            except Exception as e:
                return {"hermes_exit": None, "oracle_pass": None, "wall_clock_s": None,
                        "error": f"parse: {e}", "raw_line": line[:300]}
    return {"hermes_exit": None, "oracle_pass": None, "wall_clock_s": None,
            "error": "no __RESULT__ parsed", "raw": (proc.stdout[-600:] + proc.stderr[-400:])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="A,B")
    ap.add_argument("--regime", default="greedy")  # hermes managt Sampling intern; nur fuers Log
    ap.add_argument("--tasks", default="tasks/")
    args = ap.parse_args()

    cfg = C.load_config()
    hcfg = cfg["hermes"]
    regime = C.get_regime(args.regime, cfg)
    tasks = load_tasks(args.tasks)
    print(f"{len(tasks)} Tasks, Bench-venv vorbereiten ...")
    ensure_bench_venv()

    for model_key in args.models.split(","):
        model = C.get_model(model_key, cfg)
        home = write_bench_home(model, hcfg)
        rec = Recorder(track=1, model_key=model_key, model_id=model.model_id,
                       endpoint=model.endpoint, regime=regime.name,
                       sampling={"note": "hermes-managed", "hermes": hcfg})
        print(f"  Modell {model_key} ({model.name}) @ {model.endpoint}  home={home}")
        with rec:
            for t in tasks:
                res = run_task(model, home, t)
                rec.log_result(task_id=t["_id"], domain=t.get("domain"), **res)
                print(f"    [{model_key}] {t['_id']}: oracle_pass={res.get('oracle_pass')} "
                      f"hermes_exit={res.get('hermes_exit')} {res.get('wall_clock_s')}s")
        print(f"  -> {rec.path}")


if __name__ == "__main__":
    main()
