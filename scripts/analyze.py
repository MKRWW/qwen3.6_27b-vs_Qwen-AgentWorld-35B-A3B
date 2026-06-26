"""Aggregiert results/raw/ zu Kennzahlen je Kategorie/Modell/Regime.

Liefert die Datenbasis fuer Charts (Factuality, Token-Effizienz, Head-to-head).
Ausgabe: lesbare Tabelle + (optional) JSON via --json out.json.

Aufruf:  python scripts/analyze.py results/raw [--json docs/data/summary.json]
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


def category(triple_id: str) -> str:
    """Kategorie aus dem Triple-Prefix (errors/python/git/.../preexisting/longchain/swe)."""
    name = triple_id.replace("\\", "/").split("/")[-1]
    base = name.rsplit("_", 1)[0] if "_" in name else name
    base = base.replace(".json", "")
    # preexisting2/3, longchain2 -> Oberkategorie
    for cat in ("preexisting", "longchain", "terminal_basic"):
        if base.startswith(cat):
            return cat
    return base


def load(raw_dir: str):
    runs = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        header, results, toks = None, [], []
        for line in open(path, encoding="utf-8"):
            o = json.loads(line)
            if o.get("type") == "run_header":
                header = o
            elif o.get("type") == "result":
                results.append(o)
            elif o.get("type") == "api_call" and o.get("response"):
                ct = (o["response"].get("usage") or {}).get("completion_tokens")
                if ct:
                    toks.append(ct)
        if header:
            runs.append((header, results, toks))
    return runs


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "results/raw"
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    runs = load(raw)
    summary = {"track2": [], "track1": []}

    print("# Analyse\n\n## Track 2 — Factuality je Kategorie + Token-Effizienz\n")
    t2 = [(h, r, tk) for h, r, tk in runs if h["track"] == 2]
    for h, res, toks in t2:
        res = [r for r in res if "factuality" in r]
        if not res:
            continue
        bycat = {}
        for r in res:
            bycat.setdefault(category(r["triple_id"]), []).append(r["factuality"]["factuality"])
        cats = {c: mean(v) for c, v in sorted(bycat.items())}
        row = {"model": h["model"], "regime": h["regime"], "judge": res[0].get("judge_model"),
               "n": len(res), "factuality_overall": mean([r["factuality"]["factuality"] for r in res]),
               "tok_median": int(st.median(toks)) if toks else None,
               "tok_sum": sum(toks) if toks else None, "by_category": cats}
        summary["track2"].append(row)
        print(f"### {h['model']} ({h['regime']}, judge={row['judge']}, n={row['n']})")
        print(f"  Factuality gesamt={row['factuality_overall']}  tok_median={row['tok_median']}  tok_sum={row['tok_sum']}")
        print("  je Kategorie: " + ", ".join(f"{c}={v}" for c, v in cats.items()))
        print()

    # Head-to-head Factuality A vs B je Regime (gleiche Triples)
    print("## Track 2 — Head-to-head A vs B (Factuality, gleiche Triples)\n")
    for regime in sorted({h["regime"] for h, _, _ in t2}):
        bymodel = {}
        for h, res, _ in t2:
            if h["regime"] != regime:
                continue
            bymodel[h["model"]] = {r["triple_id"]: r["factuality"]["factuality"]
                                   for r in res if "factuality" in r}
        if set(bymodel) >= {"A", "B"}:
            ids = sorted(set(bymodel["A"]) & set(bymodel["B"]))
            aw = sum(1 for i in ids if bymodel["A"][i] - bymodel["B"][i] > 3)
            bw = sum(1 for i in ids if bymodel["B"][i] - bymodel["A"][i] > 3)
            print(f"  [{regime}] n={len(ids)}  A-mean={mean([bymodel['A'][i] for i in ids])}  "
                  f"B-mean={mean([bymodel['B'][i] for i in ids])}  A>B:{aw}  B>A:{bw}  tie:{len(ids)-aw-bw}")
    print()

    print("## Track 1 — Success-Rate je Modell\n")
    for h, res, _ in runs:
        if h["track"] != 1:
            continue
        ok = sum(1 for r in res if r.get("oracle_pass"))
        row = {"model": h["model"], "regime": h["regime"], "n": len(res), "passed": ok}
        summary["track1"].append(row)
        print(f"  {h['model']} ({h['regime']}): {ok}/{len(res)} bestanden")

    if json_out:
        os.makedirs(os.path.dirname(json_out) or ".", exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\nJSON -> {json_out}")


if __name__ == "__main__":
    main()
