"""Track-3-Aggregation -> publizierbare Tabelle + docs/data/track3_summary.json.

Liest results/raw/track3_*.jsonl, dedupliziert pro (env, task, rep) (neuere Datei
gewinnt -> Resume-sicher) und aggregiert ueber Replikate (Mittel + Spannweite).

Metriken:
  - Erfolg A@real            : oracle_pass in echter Sandbox (Baseline).
  - Erfolg A@sim Real-Replay : oracle_pass der in der Sim erzeugten Sequenz, real nachgespielt.
  - Getaeuscht-Rate          : Anteil Episoden mit said_done=True UND oracle_pass=False.
  - Divergenz/Schritt        : Anteil Schritte sim-Obs != real-Obs (ueber alle sim-Schritte).
  - Token (Median)           : A (Policy) und B (Sim) completion_tokens.

Pro-Rep-Aggregat (Erfolgsrate je Replikat ueber alle Tasks) -> Spannweite ueber Reps.

Aufruf:  python scripts/report_track3.py [results/raw] [docs/data/track3_summary.json]
"""
from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RAW = sys.argv[1] if len(sys.argv) > 1 else "results/raw"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/data/track3_summary.json"


def rng(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"mean": round(sum(xs) / len(xs), 1), "min": round(min(xs), 1),
            "max": round(max(xs), 1), "n": len(xs)}


def load_all():
    """-> (results_by_key, tokens) ; results_by_key[(env,task,rep)] = result-dict.
    Token-Liste = [(model_key, completion_tokens, env)]."""
    results = {}
    tokens = []
    files = sorted(glob.glob(os.path.join(RAW, "track3_*.jsonl")), key=os.path.getmtime)
    for f in files:
        env_hint = "sim" if "_sim_" in os.path.basename(f) else "real"
        for line in open(f, encoding="utf-8"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "result" and o.get("task") and "env" in o:
                results[(o["env"], o["task"], o.get("rep"))] = o   # neuere Datei gewinnt
            elif o.get("type") == "api_call" and o.get("response"):
                ct = (o["response"].get("usage") or {}).get("completion_tokens")
                if ct:
                    tokens.append((o.get("model_key"), ct, env_hint))
    return results, tokens


def per_rep_rates(rows, key_fn):
    """rows -> {rep: rate} mit rate = Mittel von key_fn ueber die Tasks dieses Reps."""
    by_rep = {}
    for r in rows:
        by_rep.setdefault(r.get("rep"), []).append(key_fn(r))
    return {rep: (sum(v) / len(v)) for rep, v in by_rep.items() if v}


def main():
    results, tokens = load_all()
    real = [r for (env, _, _), r in results.items() if env == "real" and not r.get("error")]
    sim = [r for (env, _, _), r in results.items() if env == "sim" and not r.get("error")]

    # --- Pro-Rep-Erfolgsraten (Spannweite ueber Reps) ---
    real_succ = per_rep_rates(real, lambda r: 1.0 if r.get("oracle_pass") else 0.0)
    sim_succ = per_rep_rates(sim, lambda r: 1.0 if r.get("oracle_pass") else 0.0)
    sim_deceived = per_rep_rates(sim, lambda r: 1.0 if r.get("deceived") else 0.0)

    # --- Divergenz/Schritt (ueber ALLE sim-Schritte, gepoolt + pro Rep) ---
    div_by_rep = {}
    for r in sim:
        if r.get("n_compared"):
            d = div_by_rep.setdefault(r.get("rep"), [0, 0])
            d[0] += r.get("n_diverge", 0)
            d[1] += r["n_compared"]
    div_rep_rates = {rep: (100.0 * a / b) for rep, (a, b) in div_by_rep.items() if b}
    tot_div = sum(a for a, b in div_by_rep.values())
    tot_cmp = sum(b for a, b in div_by_rep.values())

    # --- Tokens ---
    a_tok = [ct for mk, ct, _ in tokens if mk == "A"]
    b_tok = [ct for mk, ct, _ in tokens if mk == "B"]

    # --- Per-Task-Tabelle (Erfolg real vs sim, ueber Reps gemittelt) ---
    tasks = sorted({r["task"] for r in real} | {r["task"] for r in sim})
    per_task = {}
    for tk in tasks:
        rr = [r for r in real if r["task"] == tk]
        sr = [r for r in sim if r["task"] == tk]
        per_task[tk] = {
            "real_pass": f"{sum(1 for r in rr if r.get('oracle_pass'))}/{len(rr)}" if rr else "-",
            "sim_pass": f"{sum(1 for r in sr if r.get('oracle_pass'))}/{len(sr)}" if sr else "-",
            "sim_deceived": sum(1 for r in sr if r.get("deceived")),
            "sim_div_rate": (round(100.0 * sum(r.get("n_diverge", 0) for r in sr) /
                                   max(1, sum(r.get("n_compared", 0) for r in sr)), 1)
                             if sr and any(r.get("n_compared") for r in sr) else None),
        }

    summary = {
        "n_real_episodes": len(real), "n_sim_episodes": len(sim),
        "real_success_pct": rng([100 * v for v in real_succ.values()]),
        "sim_replay_success_pct": rng([100 * v for v in sim_succ.values()]),
        "sim_deceived_pct": rng([100 * v for v in sim_deceived.values()]),
        "divergence_per_step_pct": rng(list(div_rep_rates.values())),
        "divergence_pooled_pct": round(100.0 * tot_div / tot_cmp, 1) if tot_cmp else None,
        "n_steps_compared": tot_cmp,
        "policy_tok_median_A": round(st.median(a_tok), 0) if a_tok else None,
        "sim_tok_median_B": round(st.median(b_tok), 0) if b_tok else None,
        "per_task": per_task,
    }

    def cell(d):
        return f"{d['mean']} ({d['min']}–{d['max']})" if d else "—"

    print("# TRACK 3 — Closed-Loop: Agent (A) gegen AgentWorld (B) als Umgebung\n")
    print(f"Episoden: real={len(real)}, sim={len(sim)} (card-Regime temp0.6, "
          f"Reps={len(real_succ)}/{len(sim_succ)})\n")
    print("| Metrik | Wert (Mittel, Spannweite über Reps) |")
    print("|---|---|")
    print(f"| **Erfolg A@real** (Baseline, Oracle) | **{cell(summary['real_success_pct'])} %** |")
    print(f"| **Erfolg A@sim** (Real-Replay, Oracle) | **{cell(summary['sim_replay_success_pct'])} %** |")
    print(f"| Getäuscht-Rate (DONE, aber real gescheitert) | {cell(summary['sim_deceived_pct'])} % |")
    print(f"| Divergenz / Schritt (sim-Obs ≠ real-Obs) | {cell(summary['divergence_per_step_pct'])} %"
          f"  (gepoolt {summary['divergence_pooled_pct']} %, n={summary['n_steps_compared']}) |")
    print(f"| Token/Schritt Median — A (Policy) / B (Sim) | {summary['policy_tok_median_A']} / "
          f"{summary['sim_tok_median_B']} |")
    print("\n## Pro Task (Erfolg real vs. sim-Real-Replay, über Reps)\n")
    print("| Task | real | sim-replay | getäuscht | Divergenz/Schritt |")
    print("|---|---|---|---|---|")
    for tk in tasks:
        p = per_task[tk]
        dv = f"{p['sim_div_rate']} %" if p["sim_div_rate"] is not None else "—"
        print(f"| {tk} | {p['real_pass']} | {p['sim_pass']} | {p['sim_deceived']} | {dv} |")

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\ntrack3_summary.json -> {OUT}")


if __name__ == "__main__":
    main()
