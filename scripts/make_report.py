"""Aggregiert results/raw/*.jsonl zu Markdown-Tabellen (-> docs/FINDINGS.md).

Aufruf:  python scripts/make_report.py results/raw > docs/FINDINGS.md
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

# Windows-Konsole/Redirect ist sonst cp1252 -> UnicodeEncodeError bei → / —
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def read_runs(raw_dir: str):
    runs = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        header, results, toks = None, [], []
        with open(path, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                if obj.get("type") == "run_header":
                    header = obj
                elif obj.get("type") == "result":
                    results.append(obj)
                elif obj.get("type") == "api_call" and obj.get("response"):
                    ct = (obj["response"].get("usage") or {}).get("completion_tokens")
                    if ct:
                        toks.append(ct)
        if header:
            header["_tokens"] = toks
            runs.append((header, results))
    return runs


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def report_track1(runs):
    print("## Track 1 — Hype-Test (Policy / Agent)\n")
    print("| Modell | Regime | Tasks | Success-Rate | hermes-Fehler |")
    print("|--------|--------|-------|--------------|---------------|")
    for h, res in runs:
        if h["track"] != 1:
            continue
        ok = sum(1 for r in res if r.get("oracle_pass"))
        errs = sum(1 for r in res if r.get("hermes_exit") not in (0, None))
        rate = f"{ok}/{len(res)}" if res else "0/0"
        print(f"| {h['model']} | {h['regime']} | {len(res)} | {rate} | {errs} |")
    print()


def report_track2(runs):
    print("## Track 2 — World-Model-Fidelity\n")
    print("| Modell | Regime | Triples | Factuality | Format | tok(median) | Consist.* |")
    print("|--------|--------|---------|-----------|--------|-------------|-----------|")
    for h, res in runs:
        if h["track"] != 2:
            continue
        fact = mean([r["factuality"]["factuality"] for r in res])
        fmt = mean([r["format"]["format"] for r in res])
        con = mean([(r.get("judge") or {}).get("consistency") for r in res])
        tok = _median(h.get("_tokens", []))
        print(f"| {h['model']} | {h['regime']} | {len(res)} | {fact} | {fmt} | "
              f"{tok} | {con} |")
    print("\n*Realism/Quality des LLM-Judge sind hier nicht vertrauenswürdig "
          "(unkalibrierte Cross-Judges) — siehe FINDINGS.md. tok = completion_tokens "
          "(Effizienz, fair vergleichbar).\n")


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "results/raw"
    runs = read_runs(raw_dir)
    print("# FINDINGS — AgentWorld-35B-A3B vs Qwen3.6-27b\n")
    print("> Auto-generiert von scripts/make_report.py. **Vor dem Zitieren "
          "docs/THREATS.md + FINDINGS.md lesen** (int4 vs NVFP4, nur Terminal, N=26, "
          "Ceiling-Effekt).\n")
    if not runs:
        print("_Noch keine Runs in results/raw/._")
        return
    report_track1(runs)
    report_track2(runs)
    print("## Interpretation\n")
    print("- Hält Hypothese 1 (AgentWorld schwächer als Policy)?  → siehe Track-1-Tabelle.")
    print("- Hält Hypothese 2 (AgentWorld stärker als World Model)? → siehe Track-2-Tabelle.")
    print("- Erinnerung: kleine Stichprobe, Richtungs-Indikator, kein p-Wert.")


if __name__ == "__main__":
    main()
