"""Track 3 — Closed-Loop: ein echter ReAct-Agent (Policy = Modell A) laeuft gegen
zwei austauschbare Umgebungen:

  * env=real  : echte WSL-Sandbox (Baseline / Kontrolle, Oracle = Wahrheit).
  * env=sim   : AgentWorld (Modell B) sagt die naechste Terminal-Observation voraus
                (exakt das Track-2-Setup). Closed-Loop: B konditioniert auf seine
                EIGENEN frueheren Vorhersagen -> Fehler koennen sich aufschaukeln.

Gemessen (>=2 Replikate, Mittel +- Spannweite, Aggregation in scripts/report_track3.py):
  1. Erfolg A@real            (Oracle in echter Sandbox).
  2. Erfolg A@sim REAL-REPLAY (die in der Sim erzeugte Befehlssequenz in frischer
     echter Sandbox nachgespielt + Oracle).
  3. Getaeuscht-Rate         (Agent sagt DONE/glaubt Erfolg, Real-Replay scheitert).
  4. Divergenz/Schritt       (Anteil Schritte, an denen sim-Observation != real-Obs;
     jeder sim-Befehl wird parallel real ausgefuehrt -> Aufschaukeln sichtbar).

Ausfuehrungs-Modell (robust auf Windows, kein interaktiver Pipe-State):
  Jede reale Auswertung = REINE FUNKTION run_sequence(task, commands): frische
  WSL-Sandbox -> setup.sh seedet -> die GANZE Befehlssequenz in EINEM persistenten
  bash-Driver (gen_triples-Muster, cd/export persistieren) -> pro Schritt Marker
  (stdout/stderr/exit/cwd/fs_delta, base64) -> optional oracle.sh. Idempotent &
  deterministisch, da jede Invocation frisch seedet + voll nachspielt.

Aufruf:
  python harness/run_track3_closedloop.py --env real --reps 2
  python harness/run_track3_closedloop.py --env sim  --reps 2
  python harness/run_track3_closedloop.py --env real --tasks create_file --reps 1   # smoke
"""
from __future__ import annotations

import argparse
import base64
import difflib
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import client as C            # noqa: E402
from record import Recorder   # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_DIR = os.path.join(HERE, "tasks", "closedloop")
PROMPT_DIR = os.path.join(HERE, "config", "prompts")
MARK = "@@STEP@@"
OMARK = "@@ORACLE@@"
# Kanonischer Prompt fuer die synthetisierten/sim Terminal-Screens. Statisch, damit
# B ein konsistentes Format nachahmt; die Policy sieht ohnehin nur den OUTPUT (ohne
# Prompt), daher kein cwd-Confound fuer die Policy.
CANON_PROMPT = "root@agentworld:/app#"

# ---------------------------------------------------------------------------
# 1) Tasks laden
# ---------------------------------------------------------------------------

def load_tasks(filt: list[str] | None) -> list[dict]:
    out = []
    for tj in sorted(glob.glob(os.path.join(TASKS_DIR, "*", "task.json"))):
        d = os.path.dirname(tj)
        with open(tj, encoding="utf-8") as f:
            t = json.load(f)
        t["_dir"] = d
        t["setup"] = open(os.path.join(d, "setup.sh"), encoding="utf-8").read()
        t["oracle"] = open(os.path.join(d, "oracle.sh"), encoding="utf-8").read()
        if filt and t["name"] not in filt:
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# 2) WSL-Executor: reine Funktion (frische Sandbox -> setup -> replay -> oracle)
# ---------------------------------------------------------------------------

def _b64d(s: str) -> str:
    return base64.b64decode(s).decode("utf-8", "replace") if s else ""


def _build_driver(setup_sh: str, commands: list[str], oracle_sh: str | None) -> str:
    """Bash-Driver: frische Sandbox, setup, alle Befehle in DERSELBEN Shell (cd/export
    persistieren via Brace-Group + Redirect statt $()-Subshell), pro Schritt ein
    base64-Marker. Optional oracle.sh am Ende. Temp-Dateien in /tmp (tauchen nicht im
    Sandbox-`ls` auf)."""
    setup_b64 = base64.b64encode(setup_sh.encode("utf-8")).decode()
    lines = [
        "set +e",
        "____sb=$(mktemp -d)",
        f'echo "{setup_b64}" | base64 -d > /tmp/__setup.$$.sh',
        'cd "$____sb" || exit 99',
        # setup im Sandbox-cwd ausfuehren (seedet relative Dateien)
        "bash /tmp/__setup.$$.sh >/tmp/__setuplog.$$ 2>&1",
    ]
    for i, action in enumerate(commands):
        o, e = f"/tmp/__o.$$.{i}", f"/tmp/__e.$$.{i}"
        lines += [
            "____before=$(ls -1A 2>/dev/null)",
            f"{{ {action} ; }} > {o} 2> {e} ; ____ec=$?",
            f"____out=$(cat {o}); ____err=$(cat {e}); rm -f {o} {e}",
            "____after=$(ls -1A 2>/dev/null)",
            "____delta=$(comm -13 <(echo \"$____before\"|sort) <(echo \"$____after\"|sort))",
            f'echo "{MARK}{i}|$(echo -n "$____out"|base64 -w0)|$(echo -n "$____err"|base64 -w0)'
            f'|$____ec|$(echo -n "$(pwd)"|base64 -w0)|$(echo -n "$____delta"|base64 -w0)"',
        ]
    if oracle_sh is not None:
        ob64 = base64.b64encode(oracle_sh.encode("utf-8")).decode()
        lines += [
            f'echo "{ob64}" | base64 -d > /tmp/__oracle.$$.sh',
            "bash /tmp/__oracle.$$.sh >/dev/null 2>&1 ; ____orc=$?",
            f'echo "{OMARK}$____orc"',
            "rm -f /tmp/__oracle.$$.sh",
        ]
    lines += ['rm -f /tmp/__setup.$$.sh /tmp/__setuplog.$$', 'rm -rf "$____sb"']
    return "\n".join(lines)


def run_sequence(task: dict, commands: list[str], run_oracle: bool = False,
                 timeout: int = 120) -> dict:
    """Befehlssequenz in frischer Sandbox real ausfuehren. Gibt pro Schritt
    {stdout,stderr,exit_code,cwd,fs_delta} + optional oracle_pass zurueck.
    Bei Timeout/Fehler: 'error' gesetzt, steps so weit wie geliefert."""
    driver = _build_driver(task["setup"], commands, task["oracle"] if run_oracle else None)
    try:
        proc = subprocess.run(["wsl.exe", "-e", "bash", "-lc", driver],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"steps": [], "oracle_pass": None, "error": f"timeout>{timeout}s"}
    steps: dict[int, dict] = {}
    oracle_pass = None
    for line in proc.stdout.splitlines():
        if line.startswith(MARK):
            idx, out_b, err_b, ec, pwd_b, delta_b = line[len(MARK):].split("|")
            steps[int(idx)] = {
                "stdout": _b64d(out_b), "stderr": _b64d(err_b), "exit_code": int(ec),
                "cwd": _b64d(pwd_b),
                "fs_delta": [x for x in _b64d(delta_b).splitlines() if x.strip()],
            }
        elif line.startswith(OMARK):
            oracle_pass = (line[len(OMARK):].strip() == "0")
    ordered = [steps.get(i) for i in range(len(commands))]
    return {"steps": ordered, "oracle_pass": oracle_pass, "error": None,
            "stderr_driver": proc.stderr.strip()[:500] or None}


def obs_from_step(step: dict | None) -> str:
    """Normalisierte Observation (was die Policy sieht): stdout + stderr, getrimmt."""
    if step is None:
        return "(no output captured)"
    parts = []
    if step["stdout"].strip():
        parts.append(step["stdout"].rstrip("\n"))
    if step["stderr"].strip():
        parts.append(step["stderr"].rstrip("\n"))
    body = "\n".join(parts).strip()
    return body if body else "(no output; exit code %d)" % step["exit_code"]


def raw_output(step: dict | None) -> str:
    """Reiner Befehls-Output (stdout+stderr), getrimmt, OHNE Platzhalter — fuer den
    Divergenz-Vergleich (sim-Extraktion liefert ebenfalls reinen Output)."""
    if step is None:
        return ""
    out = step["stdout"].rstrip("\n")
    if step["stderr"].strip():
        out = (out + "\n" + step["stderr"].rstrip("\n")) if out.strip() else step["stderr"].rstrip("\n")
    return out.strip()


def screen_from_step(cmd: str, step: dict | None) -> str:
    """Realen Schritt als Terminal-Screen formatieren (fuer B's Grounding-History,
    damit B im trainierten Format konditioniert wird)."""
    out = ""
    if step is not None:
        out = step["stdout"]
        if step["stderr"].strip():
            out = (out.rstrip("\n") + "\n" + step["stderr"]) if out.strip() else step["stderr"]
    out = out.rstrip("\n")
    body = (out + "\n") if out else ""
    return f"{CANON_PROMPT} {cmd}\n{body}{CANON_PROMPT}"


# ---------------------------------------------------------------------------
# 3) Sim-Umgebung: B sagt den naechsten Screen voraus (Track-2-Setup)
# ---------------------------------------------------------------------------

def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text or "", flags=re.S).strip()


_PROMPT_RE = re.compile(r"^\s*\S+@\S+:[^#$]*[#$]\s?")  # generischer Shell-Prompt


def extract_output_from_screen(screen: str, cmd: str) -> str:
    """Aus B's vorhergesagtem Screen die reine Befehls-Ausgabe ziehen: die Zeile mit
    dem Echo des Befehls finden, danach bis zum naechsten Prompt sammeln. Faellt zurueck
    auf 'alle Nicht-Prompt-Zeilen', wenn das Echo nicht gefunden wird (immer geloggt)."""
    lines = (screen or "").splitlines()
    # 1) Zeile finden, die den Befehl echo't (Prompt + cmd am Zeilenende)
    echo_idx = None
    for i, ln in enumerate(lines):
        if cmd.strip() and ln.rstrip().endswith(cmd.strip()):
            echo_idx = i
            break
    if echo_idx is not None:
        out = []
        for ln in lines[echo_idx + 1:]:
            if _PROMPT_RE.match(ln):
                break
            out.append(ln)
        return "\n".join(out).strip()
    # 2) Fallback: alle Zeilen, die nicht wie ein Prompt aussehen
    out = [ln for ln in lines if not _PROMPT_RE.match(ln)]
    return "\n".join(out).strip()


def terminal_system_prompt() -> str:
    with open(os.path.join(PROMPT_DIR, "terminal", "system_prompt.txt"), encoding="utf-8") as f:
        return f.read()


def sim_predict(cli: C.Client, b_messages: list[dict], cmd: str, max_tokens: int) -> tuple[str, str, dict]:
    """Ein Sim-Schritt: B sagt den Screen fuer `cmd` voraus (gegeben b_messages-History,
    die B's EIGENE fruehere Screens enthaelt). Gibt (clean_output, raw_screen, resp)."""
    msgs = b_messages + [{"role": "user", "content": f"Action: execute_bash\nCommand: {cmd}"}]
    resp = cli.chat(msgs, max_tokens=max_tokens)  # thinking AN (Default)
    screen = _strip_think(C.first_text(resp))
    clean = extract_output_from_screen(screen, cmd)
    return clean, screen, resp


# ---------------------------------------------------------------------------
# 4) Policy = Modell A (ReAct, CMD: / DONE)
# ---------------------------------------------------------------------------

POLICY_SYSTEM = (
    "You are an autonomous shell agent solving a task in a Linux bash environment.\n"
    "You work in a FIXED working directory; always use RELATIVE paths (never absolute "
    "paths, never cd outside it). Issue ONE command at a time and read its output.\n\n"
    "Respond EACH turn with EXACTLY ONE line, nothing else:\n"
    "  CMD: <a single shell command>\n"
    "or, only when the task is fully complete:\n"
    "  DONE\n\n"
    "Do not explain. Do not use markdown. Output only the `CMD: ...` line or `DONE`."
)

_CMD_RE = re.compile(r"^\s*CMD:\s*(.+?)\s*$", re.I | re.M)


def parse_policy(text: str) -> tuple[str, str | None]:
    """-> ('done', None) | ('cmd', command) | ('none', None)."""
    t = _strip_think(text)
    if re.search(r"(?m)^\s*DONE\s*$", t) and not _CMD_RE.search(t):
        return "done", None
    m = _CMD_RE.search(t)
    if m:
        cmd = m.group(1).strip().strip("`")
        return "cmd", cmd
    # Fallback: einzelne ```bash``` Zeile
    fb = re.search(r"```(?:bash|sh)?\s*\n(.+?)\n```", t, re.S)
    if fb:
        return "cmd", fb.group(1).strip().splitlines()[0].strip()
    if re.search(r"\bDONE\b", t):
        return "done", None
    return "none", None


def policy_decide(cli: C.Client, messages: list[dict], max_tokens: int) -> tuple[str, str | None, str]:
    """Policy-Call mit 1 Retry bei leerer/unparsbarer Antwort. -> (kind, cmd, raw)."""
    for attempt in (1, 2):
        resp = cli.chat(messages, max_tokens=max_tokens)  # thinking AN (Default)
        raw = C.first_text(resp)
        kind, cmd = parse_policy(raw)
        if kind != "none":
            return kind, cmd, raw
    return "none", None, raw


# ---------------------------------------------------------------------------
# 5) Episode-Runner
# ---------------------------------------------------------------------------

def _policy_user(obs: str) -> str:
    return f"Output:\n{obs}\n\nRespond with `CMD: <command>` or `DONE`."


def run_episode_real(task: dict, policy_cli: C.Client, rec: Recorder, rep: int,
                     policy_max: int) -> dict:
    """A@real: Policy lebt in der echten Sandbox. Jeder Schritt = run_sequence der
    bisherigen Befehle, letzte Observation zurueck an die Policy. Oracle am Ende."""
    boot = run_sequence(task, ["ls -la"], run_oracle=False)
    boot_obs = obs_from_step(boot["steps"][0] if boot["steps"] else None)
    messages = [
        {"role": "system", "content": POLICY_SYSTEM},
        {"role": "user", "content": f"Task: {task['goal']}\n\nThe working directory "
         f"currently contains (`ls -la`):\n{boot_obs}\n\nRespond with `CMD: <command>` "
         f"or `DONE`."},
    ]
    commands: list[str] = []
    trace = []
    said_done = False
    status = "max_steps"
    for stepno in range(task["max_steps"]):
        kind, cmd, raw = policy_decide(policy_cli, messages, policy_max)
        if kind == "none":
            status = "policy_empty"
            trace.append({"step": stepno, "kind": "none", "raw": raw[:400]})
            break
        if kind == "done":
            said_done = True
            status = "done"
            trace.append({"step": stepno, "kind": "done"})
            break
        commands.append(cmd)
        seq = run_sequence(task, commands, run_oracle=False)
        if seq["error"]:
            status = f"env_error:{seq['error']}"
            trace.append({"step": stepno, "cmd": cmd, "error": seq["error"]})
            break
        step = seq["steps"][-1] if seq["steps"] else None
        obs = obs_from_step(step)
        trace.append({"step": stepno, "cmd": cmd, "obs": obs[:600],
                      "exit": step["exit_code"] if step else None})
        messages += [{"role": "assistant", "content": f"CMD: {cmd}"},
                     {"role": "user", "content": _policy_user(obs)}]
    final = run_sequence(task, commands, run_oracle=True)
    oracle_pass = bool(final["oracle_pass"])
    res = {"task": task["name"], "env": "real", "rep": rep, "status": status,
           "said_done": said_done, "n_steps": len(commands), "commands": commands,
           "oracle_pass": oracle_pass, "deceived": said_done and not oracle_pass,
           "trace": trace}
    rec.log_result(**res)
    return res


def run_episode_sim(task: dict, policy_cli: C.Client, sim_cli: C.Client, rec: Recorder,
                    rep: int, policy_max: int, sim_max: int) -> dict:
    """A@sim: Policy lebt in der von B simulierten Umgebung. Pro Schritt sagt B den
    Screen voraus (konditioniert auf B's EIGENE frueheren Screens) -> Closed-Loop.
    Parallel wird jeder Befehl real nachgespielt (Divergenz + Real-Replay + Oracle)."""
    # Bootstrap: realer `ls -la` als gemeinsamer Startzustand (Env "initialisiert").
    boot = run_sequence(task, ["ls -la"], run_oracle=False)
    boot_step = boot["steps"][0] if boot["steps"] else None
    boot_obs = obs_from_step(boot_step)
    boot_screen = screen_from_step("ls -la", boot_step)

    messages = [
        {"role": "system", "content": POLICY_SYSTEM},
        {"role": "user", "content": f"Task: {task['goal']}\n\nThe working directory "
         f"currently contains (`ls -la`):\n{boot_obs}\n\nRespond with `CMD: <command>` "
         f"or `DONE`."},
    ]
    # B's Konversation: Terminal-World-Model-Prompt + Bootstrap-Screen als Grounding.
    b_messages = [
        {"role": "system", "content": terminal_system_prompt()},
        {"role": "user", "content": "Action: execute_bash\nCommand: ls -la"},
        {"role": "assistant", "content": boot_screen},
    ]
    commands: list[str] = []
    trace = []
    n_diverge = 0
    n_compared = 0
    n_sim_empty = 0
    said_done = False
    status = "max_steps"
    for stepno in range(task["max_steps"]):
        kind, cmd, raw = policy_decide(policy_cli, messages, policy_max)
        if kind == "none":
            status = "policy_empty"
            trace.append({"step": stepno, "kind": "none", "raw": raw[:400]})
            break
        if kind == "done":
            said_done = True
            status = "done"
            trace.append({"step": stepno, "kind": "done"})
            break
        commands.append(cmd)
        # --- Sim-Vorhersage (B) ---
        try:
            sim_obs, sim_screen, _ = sim_predict(sim_cli, b_messages, cmd, sim_max)
        except Exception as ex:  # noqa: BLE001 — B-Infra-Fehler killt nicht die Episode
            sim_obs, sim_screen = "(no output captured)", ""
            trace.append({"step": stepno, "cmd": cmd, "sim_error": repr(ex)[:200]})
        sim_empty = not sim_screen.strip()
        if sim_empty:
            n_sim_empty += 1
        # B's eigene Vorhersage wird zur History (Closed-Loop)
        b_messages += [{"role": "user", "content": f"Action: execute_bash\nCommand: {cmd}"},
                       {"role": "assistant", "content": sim_screen or CANON_PROMPT}]
        # --- Realer Schatten-Schritt (Divergenz) ---
        shadow = run_sequence(task, commands, run_oracle=False)
        shadow_step = shadow["steps"][-1] if shadow["steps"] and shadow["steps"][-1] else None
        real_obs = obs_from_step(shadow_step)            # policy-facing (mit Platzhalter)
        # Divergenz auf REINEM Output vergleichen (kein Platzhalter -> kein Artefakt:
        # "kein Output real" == "kein Output sim"). Leere Sim-Vorhersage zaehlt als
        # divergent NUR wenn real Output erwartet wuerde.
        real_cmp = raw_output(shadow_step)
        sim_cmp = sim_obs.strip()
        ratio = difflib.SequenceMatcher(None, real_cmp, sim_cmp).ratio()
        diverged = ratio < 0.999
        n_compared += 1
        if diverged:
            n_diverge += 1
        trace.append({"step": stepno, "cmd": cmd, "sim_obs": sim_obs[:600],
                      "real_obs": real_obs[:600], "sim_empty": sim_empty,
                      "diverged": diverged, "match_ratio": round(ratio, 3),
                      "exit_real": shadow_step["exit_code"] if shadow_step else None})
        # Policy sieht die SIM-Observation (lebt in der Simulation)
        messages += [{"role": "assistant", "content": f"CMD: {cmd}"},
                     {"role": "user", "content": _policy_user(sim_obs)}]
    # --- Real-Replay + Oracle: die in der Sim erzeugte Sequenz in frischer Sandbox ---
    replay = run_sequence(task, commands, run_oracle=True)
    oracle_pass = bool(replay["oracle_pass"])
    res = {"task": task["name"], "env": "sim", "rep": rep, "status": status,
           "said_done": said_done, "n_steps": len(commands), "commands": commands,
           "oracle_pass": oracle_pass, "deceived": said_done and not oracle_pass,
           "n_sim_empty": n_sim_empty, "n_diverge": n_diverge, "n_compared": n_compared,
           "divergence_rate": round(n_diverge / n_compared, 3) if n_compared else None,
           "trace": trace}
    rec.log_result(**res)
    return res


# ---------------------------------------------------------------------------
# 6) main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", choices=["real", "sim"], required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--tasks", default=None, help="Komma-Liste von Task-Namen (sonst alle)")
    ap.add_argument("--regime", default="card", help="Sampling-Regime (Default card=temp0.6)")
    ap.add_argument("--policy-max", type=int, default=3072)
    ap.add_argument("--sim-max", type=int, default=16384)
    ap.add_argument("--start-rep", type=int, default=0, help="Replikat-Index-Offset (Resume)")
    args = ap.parse_args()

    cfg = C.load_config()
    regime = C.get_regime(args.regime, cfg)
    filt = [s for s in args.tasks.split(",")] if args.tasks else None
    tasks = load_tasks(filt)
    print(f"{len(tasks)} Tasks, env={args.env}, reps={args.reps}, regime={args.regime}")

    a_model = C.get_model("A", cfg)
    rec = Recorder(track=3, model_key=("A" if args.env == "real" else "AvsB"),
                   model_id=a_model.model_id, endpoint=a_model.endpoint,
                   regime=f"{args.regime}_{args.env}", sampling=regime.params)
    policy_cli = C.make_client(a_model, regime, recorder=rec, timeout=150.0, max_retries=2)
    sim_cli = None
    if args.env == "sim":
        b_model = C.get_model("B", cfg)
        sim_cli = C.make_client(b_model, regime, recorder=rec, timeout=240.0, max_retries=2)

    with rec:
        for rep in range(args.start_rep, args.start_rep + args.reps):
            for t in tasks:
                try:
                    if args.env == "real":
                        r = run_episode_real(t, policy_cli, rec, rep, args.policy_max)
                        extra = ""
                    else:
                        r = run_episode_sim(t, policy_cli, sim_cli, rec, rep,
                                            args.policy_max, args.sim_max)
                        extra = (f" div={r['divergence_rate']} sim_empty={r['n_sim_empty']}")
                    print(f"  [{args.env} rep{rep}] {t['name']:<13} status={r['status']:<12} "
                          f"steps={r['n_steps']} oracle={'PASS' if r['oracle_pass'] else 'fail'} "
                          f"deceived={r['deceived']}{extra}")
                except Exception as ex:  # noqa: BLE001 — ein Task-Fehler killt nicht den Lauf
                    rec.log_result(task=t["name"], env=args.env, rep=rep,
                                   error=repr(ex)[:400])
                    print(f"  [{args.env} rep{rep}] {t['name']:<13} EPISODE-FEHLER -> {ex!r}")
    print(f"-> {rec.path}")


if __name__ == "__main__":
    main()
