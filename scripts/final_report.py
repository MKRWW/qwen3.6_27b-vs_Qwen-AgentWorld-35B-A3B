"""Finale Aggregation ueber alle Replikate -> publizierbare Tabelle + summary.json.

Pro Modell, ueber die Replikate gemittelt (mit Spannweite):
  - det. Factuality (Recall), neutraler-Judge Factuality, Empty-Rate, Token-Median
  - je Kategorie (det + judge)
Plus Track-1-Pass-Raten.

Aufruf:  python scripts/final_report.py [results/raw] [docs/data/summary.json]
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
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/data/summary.json"


def cat(tid):
    n = tid.replace("\\", "/").split("/")[-1].replace(".json", "")
    b = n.rsplit("_", 1)[0] if "_" in n else n
    for c in ("preexisting", "longchain", "terminal_basic"):
        if b.startswith(c):
            return c
    return b


def rng(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"mean": round(sum(xs) / len(xs), 1), "min": round(min(xs), 1), "max": round(max(xs), 1), "n": len(xs)}


def load_file(f):
    results, calls = [], []
    header = None
    for line in open(f, encoding="utf-8"):
        o = json.loads(line)
        if o.get("type") == "run_header":
            header = o
        elif o.get("type") == "result":
            results.append(o)
        elif o.get("type") == "api_call" and o.get("response"):
            ct = (o["response"].get("usage") or {}).get("completion_tokens")
            if ct:
                calls.append((o.get("model_key"), ct))
    toks = [ct for mk, ct in calls if mk == (header or {}).get("model")]
    return results, toks


def model_summary(mk):
    files = sorted(glob.glob(os.path.join(RAW, f"track2_{mk}_card_*.jsonl")), key=os.path.getmtime)
    reps = []
    cat_det, cat_jud = {}, {}
    for f in files:
        res, toks = load_file(f)
        if len(res) < 1:
            continue
        det = [r["factuality"]["factuality"] for r in res if "factuality" in r]
        jud = [r["judge"]["factuality"] for r in res
               if r.get("judge") and not r.get("empty") and r["judge"].get("factuality") is not None]
        reps.append({"det_fact": sum(det) / len(det), "judge_fact": (sum(jud) / len(jud)) if jud else None,
                     "empty": sum(1 for r in res if r.get("empty")), "n": len(res),
                     "tok_median": st.median(toks) if toks else None})
        for r in res:
            c = cat(r["triple_id"])
            cat_det.setdefault(c, []).append(r["factuality"]["factuality"])
            if r.get("judge") and not r.get("empty") and r["judge"].get("factuality") is not None:
                cat_jud.setdefault(c, []).append(r["judge"]["factuality"])
    return {
        "replicates": len(reps),
        "det_factuality": rng([r["det_fact"] for r in reps]),
        "judge_factuality": rng([r["judge_fact"] for r in reps]),
        "empty_per_81": rng([r["empty"] for r in reps]),
        "tok_median": rng([r["tok_median"] for r in reps]),
        "by_category_det": {c: round(sum(v) / len(v), 1) for c, v in sorted(cat_det.items())},
        "by_category_judge": {c: round(sum(v) / len(v), 1) for c, v in sorted(cat_jud.items())},
    }


def track1():
    out = {}
    for f in glob.glob(os.path.join(RAW, "track1_*_greedy_*.jsonl")):
        mk = "A" if "_A_" in f else "B"
        res = [json.loads(l) for l in open(f, encoding="utf-8") if json.loads(l).get("type") == "result"]
        out[mk] = {"passed": sum(1 for r in res if r.get("oracle_pass")), "n": len(res)}
    return out


summary = {"models": {mk: model_summary(mk) for mk in ("A", "B")}, "track1": track1()}

A, B = summary["models"]["A"], summary["models"]["B"]
print("# FINALE BILANZ — AgentWorld-35B-A3B (B) vs Qwen3.6-27B (A)\n")
print(f"Replikate: A={A['replicates']}, B={B['replicates']} (card-Regime, neutraler Judge mistral-small)\n")
print("| Metrik | A = Qwen3.6-27B | B = AgentWorld-35B |")
print("|---|---|---|")
def cell(d): return f"{d['mean']} ({d['min']}–{d['max']})" if d else "—"
print(f"| Genauigkeit — det. Recall | {cell(A['det_factuality'])} | {cell(B['det_factuality'])} |")
print(f"| Genauigkeit — neutraler Judge | {cell(A['judge_factuality'])} | {cell(B['judge_factuality'])} |")
print(f"| Leere Antworten / 81 | {cell(A['empty_per_81'])} | {cell(B['empty_per_81'])} |")
print(f"| Token / Vorhersage (Median) | {cell(A['tok_median'])} | {cell(B['tok_median'])} |")
t1 = summary["track1"]
print(f"| Track 1 (Agent-Tasks) | {t1.get('A',{}).get('passed')}/{t1.get('A',{}).get('n')} | {t1.get('B',{}).get('passed')}/{t1.get('B',{}).get('n')} |")
if B['tok_median'] and A['tok_median'] and A['tok_median']['mean']:
    print(f"\nToken-Faktor B/A ≈ {round(B['tok_median']['mean']/A['tok_median']['mean'],1)}×")

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"\nsummary.json -> {OUT}")
