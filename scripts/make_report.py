"""Aggregiert results/raw/*.jsonl zu Markdown-Tabellen (-> docs/FINDINGS.md).

Aufruf:  python scripts/make_report.py results/raw > docs/FINDINGS.md
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict


def read_runs(raw_dir: str):
    runs = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.jsonl"))):
        header, results = None, []
        with open(path, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                if obj.get("type") == "run_header":
                    header = obj
                elif obj.get("type") == "result":
                    results.append(obj)
        if header:
            runs.append((header, results))
    return runs


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def report_track1(runs):
    print("## Track 1 — Hype-Test (Policy / Agent)\n")
    print("| Modell | Regime | Tasks | Success-Rate | Crashes |")
    print("|--------|--------|-------|--------------|---------|")
    for h, res in runs:
        if h["track"] != 1:
            continue
        succ = [r["oracle"].get("success") for r in res]
        ok = sum(1 for s in succ if s)
        crashes = sum(1 for r in res if r["run"].get("crash"))
        rate = f"{ok}/{len(res)}" if res else "0/0"
        print(f"| {h['model']} | {h['regime']} | {len(res)} | {rate} | {crashes} |")
    print()


def report_track2(runs):
    print("## Track 2 — World-Model-Fidelity\n")
    print("| Modell | Regime | Triples | Factuality | Format | Consist. | Realism | Quality |")
    print("|--------|--------|---------|-----------|--------|----------|---------|---------|")
    for h, res in runs:
        if h["track"] != 2:
            continue
        fact = mean([r["factuality"]["factuality"] for r in res])
        fmt = mean([r["format"]["format"] for r in res])
        con = mean([(r.get("judge") or {}).get("consistency") for r in res])
        rea = mean([(r.get("judge") or {}).get("realism") for r in res])
        qua = mean([(r.get("judge") or {}).get("quality") for r in res])
        print(f"| {h['model']} | {h['regime']} | {len(res)} | {fact} | {fmt} | "
              f"{con} | {rea} | {qua} |")
    print()


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "results/raw"
    runs = read_runs(raw_dir)
    print("# FINDINGS — AgentWorld-35B-A3B vs Qwen3.6-27b\n")
    print("> Auto-generiert von scripts/make_report.py. **Vor dem Zitieren "
          "docs/THREATS.md lesen** (int4 vs bf16, LAN vs Remote, kleine N).\n")
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
