"""Track 3c — State-Consistency-Probe (beantwortet Markus Gärtners 2. Frage direkt):
„Wenn ich etwas POSTe, gibt mir das Modell bei einem späteren GET den Datensatz zurück?
Bildet es jede Änderung verlässlich ab?"

Statt den Agenten wandern zu lassen, treiben wir eine DETERMINISTISCHE Sequenz gegen B
(AgentWorld) im Closed-Loop und messen **exakten Recall als Funktion der Distanz**:
  * POST  = `echo "<TOKEN>" > store_x.txt`  (Wert ist im Command SICHTBAR -> ein perfekter
            State-Tracker MUSS ihn beim GET zurückgeben; isoliert Zustands-Buchhaltung vom
            Inhalt-Erraten).
  * GET   = `cat store_x.txt`  -> stimmt B's vorhergesagte Ausgabe exakt mit dem zuletzt
            geschriebenen Wert überein?  Distanz = #Schritte seit dem letzten Schreiben.
  * UPDATE= erneutes POST mit neuem Wert (überschreiben) -> liefert ein späterer GET den
            NEUEN Wert (Änderung abgebildet) oder den veralteten?

Ground truth = EIN realer WSL-Replay der ganzen Sequenz (deterministisch). Frugal: nur
~1 B-Call pro Schritt. Oracle-basiert, kein Judge, 0 € extern (B läuft auf eigener Infra).

Aufruf:  python harness/run_state_consistency.py --reps 2
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import client as C            # noqa: E402
import run_track3_closedloop as T  # noqa: E402
from record import Recorder   # noqa: E402


# --- Deterministische Probe: (op, store, value) ---------------------------------
# op: 'post' (schreiben), 'put' (überschreiben), 'get' (lesen+prüfen), 'fill' (Störung).
# Werte sind willkürlich aussehende, aber im Command SICHTBARE Tokens (kein Erraten nötig).
PROBE = [
    ("post", "a", "ALPHA-7Q2"),
    ("post", "b", "BETA-X4K9"),
    ("post", "c", "GAMMA-9ZL"),
    ("post", "d", "DELTA-3RP"),
    ("get",  "a", None),                 # dist 4
    ("fill", "ls", None),
    ("get",  "b", None),                 # dist 5
    ("fill", "echo scratch > note.txt", None),
    ("get",  "c", None),                 # dist 6
    ("fill", "mkdir sub", None),
    ("get",  "a", None),                 # dist 10
    ("fill", "wc -c store_d.txt", None),
    ("put",  "a", "ALPHA2-Z88"),         # UPDATE von a
    ("fill", "ls -1", None),
    ("get",  "a", None),                 # dist 2 nach Update -> erwartet NEUEN Wert
    ("get",  "d", None),                 # dist 11
    ("fill", "rm note.txt", None),
    ("get",  "b", None),                 # dist 16
    ("get",  "c", None),                 # dist 16
    ("get",  "a", None),                 # dist 7 nach Update -> NEUER Wert
    ("fill", "ls -la", None),
    ("get",  "a", None),                 # dist 9 nach Update -> NEUER Wert
]


def build_plan():
    """-> (commands, gets). gets[k] = dict(idx, store, target, distance, after_update)."""
    commands = []
    state = {}          # store -> (value, last_write_idx)
    updated = set()     # stores, die schon mal ge-put wurden
    gets = []
    for op, arg, val in PROBE:
        idx = len(commands)
        if op in ("post", "put"):
            commands.append(f'echo "{val}" > store_{arg}.txt')
            state[arg] = (val, idx)
            if op == "put":
                updated.add(arg)
        elif op == "get":
            commands.append(f"cat store_{arg}.txt")
            value, widx = state[arg]
            gets.append({"idx": idx, "store": arg, "target": value,
                         "distance": idx - widx, "after_update": arg in updated})
        else:  # fill
            commands.append(arg)
    return commands, gets


def run_rep(rep: int, sim_cli: C.Client, rec: Recorder, sim_max: int):
    commands, gets = build_plan()
    task = {"name": "state_probe", "suite": "stateconsistency", "setup": "", "oracle": "true"}

    # Ground truth: EIN realer Replay der ganzen Sequenz.
    real = T.run_sequence(task, commands, run_oracle=False, timeout=120)
    real_steps = real["steps"]

    # Bootstrap-Screen (leere Sandbox) als B-Grounding.
    boot = T.run_sequence(task, ["ls -la"], run_oracle=False)
    boot_step = boot["steps"][0] if boot["steps"] else None
    b_messages = [
        {"role": "system", "content": T.terminal_system_prompt()},
        {"role": "user", "content": "Action: execute_bash\nCommand: ls -la"},
        {"role": "assistant", "content": T.screen_from_step("ls -la", boot_step)},
    ]

    get_by_idx = {g["idx"]: g for g in gets}
    results = []
    for k, cmd in enumerate(commands):
        try:
            sim_clean, sim_screen, _ = T.sim_predict(sim_cli, b_messages, cmd, sim_max)
        except Exception as ex:  # noqa: BLE001
            sim_clean, sim_screen = "", ""
            print(f"    step {k} sim-error {ex!r}")
        b_messages += [{"role": "user", "content": f"Action: execute_bash\nCommand: {cmd}"},
                       {"role": "assistant", "content": sim_screen or T.CANON_PROMPT}]
        if k in get_by_idx:
            g = get_by_idx[k]
            real_out = T.raw_output(real_steps[k] if k < len(real_steps) else None)
            sim_out = sim_clean.strip()
            exact = (sim_out == g["target"])
            contains = (g["target"] in sim_out)
            real_ok = (real_out == g["target"])   # Sanity: real MUSS stimmen
            row = {"rep": rep, "store": g["store"], "distance": g["distance"],
                   "after_update": g["after_update"], "target": g["target"],
                   "sim_out": sim_out[:120], "real_out": real_out[:120],
                   "exact": exact, "contains": contains, "real_ok": real_ok}
            results.append(row)
            rec.log_result(suite="stateconsistency", kind="get", **row)
            flag = "OK " if exact else ("~  " if contains else "MISS")
            upd = " [UPDATE]" if g["after_update"] else ""
            print(f"    GET store_{g['store']} dist={g['distance']:>2}{upd:9} "
                  f"-> {flag} sim={sim_out!r} (target {g['target']!r}, real_ok={real_ok})")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--regime", default="card")
    ap.add_argument("--sim-max", type=int, default=16384)
    args = ap.parse_args()

    cfg = C.load_config()
    regime = C.get_regime(args.regime, cfg)
    b_model = C.get_model("B", cfg)
    rec = Recorder(track=3, model_key="B", model_id=b_model.model_id,
                   endpoint=b_model.endpoint, regime=f"{args.regime}_sim_stateconsistency",
                   sampling=regime.params)
    sim_cli = C.make_client(b_model, regime, recorder=rec, timeout=240.0, max_retries=2)

    commands, gets = build_plan()
    print(f"Probe: {len(commands)} Schritte, {len(gets)} GETs, reps={args.reps}")
    all_rows = []
    with rec:
        for rep in range(args.reps):
            print(f"  rep {rep}:")
            all_rows += run_rep(rep, sim_cli, rec, args.sim_max)

    # --- Kurz-Aggregation ---
    def rate(rows, key):
        rows = [r for r in rows if not r["after_update"]] if key == "persist" else rows
        return rows
    exact = sum(1 for r in all_rows if r["exact"])
    contains = sum(1 for r in all_rows if r["contains"])
    realok = sum(1 for r in all_rows if r["real_ok"])
    n = len(all_rows)
    upd = [r for r in all_rows if r["after_update"]]
    upd_exact = sum(1 for r in upd if r["exact"])
    print(f"\n=== State-Consistency: {n} GETs (real_ok {realok}/{n} — Sanity) ===")
    print(f"  Exakter Recall (sim):  {exact}/{n} = {100*exact/n:.0f}%")
    print(f"  Enthält Wert (sim):    {contains}/{n} = {100*contains/n:.0f}%")
    print(f"  Update korrekt (sim):  {upd_exact}/{len(upd)} (GETs nach Überschreiben)")
    print("  Recall nach Distanz:")
    by_d = {}
    for r in all_rows:
        by_d.setdefault(r["distance"], [0, 0])
        by_d[r["distance"]][0] += 1 if r["exact"] else 0
        by_d[r["distance"]][1] += 1
    for d in sorted(by_d):
        e, t = by_d[d]
        print(f"    dist {d:>2}: {e}/{t} exakt")
    print(f"\n-> {rec.path}")


if __name__ == "__main__":
    main()
