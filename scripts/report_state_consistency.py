"""Aggregiert die State-Consistency-Probe (Track 3c) -> docs/data/track3_state_summary.json
und erzeugt zwei Charts:
  track3_state_recall.png      : exakter Recall vs. Distanz (POST->GET über Zeit).
  track3_state_dissociation.png: Zustands-Buchhaltung (in-context) vs. Inhalt-Grounding
                                 (verborgene Daten) — die Kern-Dissoziation.

Aufruf:  python scripts/report_state_consistency.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "results", "raw")
DATA = os.path.join(HERE, "docs", "data")
OUTDIR = os.path.join(HERE, "docs", "charts")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUTDIR, exist_ok=True)

rows = []
for f in sorted(glob.glob(os.path.join(RAW, "track3_B_*stateconsistency*.jsonl")), key=os.path.getmtime):
    for line in open(f, encoding="utf-8"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") == "result" and o.get("kind") == "get":
            rows.append(o)

n = len(rows)
exact = sum(1 for r in rows if r["exact"])
realok = sum(1 for r in rows if r.get("real_ok"))
upd = [r for r in rows if r.get("after_update")]
upd_exact = sum(1 for r in upd if r["exact"])
persist = [r for r in rows if not r.get("after_update")]
persist_exact = sum(1 for r in persist if r["exact"])

by_d = {}
for r in rows:
    d = r["distance"]
    by_d.setdefault(d, [0, 0])
    by_d[d][0] += 1 if r["exact"] else 0
    by_d[d][1] += 1

# Inhalt-Grounding-Vergleich aus der longhorizon-Suite (Erfolg, wenn der Inhalt VERBORGEN
# war: copy_secret + multi_hop_chain — Tasks, deren Lösung von nie-gesehenem Inhalt abhängt).
hidden_success = None
lh = sorted(glob.glob(os.path.join(RAW, "track3_AvsB_card_sim_longhorizon_*.jsonl")), key=os.path.getmtime)
if lh:
    res = [json.loads(l) for l in open(lh[-1], encoding="utf-8")
           if '"type": "result"' in l]
    hid = [r for r in res if r.get("task") in ("copy_secret", "multi_hop_chain")]
    if hid:
        hidden_success = 100.0 * sum(1 for r in hid if r.get("oracle_pass")) / len(hid)

summary = {
    "n_gets": n, "real_ok": realok,
    "exact_recall_pct": round(100 * exact / n, 1) if n else None,
    "persist_recall_pct": round(100 * persist_exact / len(persist), 1) if persist else None,
    "update_recall_pct": round(100 * upd_exact / len(upd), 1) if upd else None,
    "n_updates": len(upd), "max_distance": max(by_d) if by_d else None,
    "recall_by_distance": {str(d): {"exact": e, "n": t} for d, (e, t) in sorted(by_d.items())},
    "hidden_content_success_pct": hidden_success,
}
with open(os.path.join(DATA, "track3_state_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"State-Consistency: {exact}/{n} exakt ({summary['exact_recall_pct']}%), "
      f"Update {upd_exact}/{len(upd)}, real_ok {realok}/{n}, max_dist {summary['max_distance']}")
print(f"Inhalt-Grounding (verborgen, copy_secret+multi_hop): {hidden_success}% Erfolg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams.update({"font.size": 13})
C_OK = "#4C72B0"
C_BAD = "#B5462F"

# Chart 1: Recall vs Distanz
ds = sorted(by_d)
rec = [100 * by_d[d][0] / by_d[d][1] for d in ds]
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(ds, rec, "o-", color=C_OK, lw=2.5, ms=9)
ax.set_ylim(0, 105); ax.set_xlabel("Distanz POST→GET (Schritte dazwischen)")
ax.set_ylabel("Exakter Recall (%)")
ax.set_title("POST→GET über Zeit: gibt B den geschriebenen Wert zurück?\n"
             "(in-context geschriebene Werte, inkl. Updates)", fontsize=14, fontweight="bold", pad=12)
for d, r in zip(ds, rec):
    ax.text(d, r - 6, f"{r:.0f}", ha="center", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.axhline(100, ls="--", color="#999", lw=1)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "track3_state_recall.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/track3_state_recall.png")

# Chart 2: Dissoziation — Zustands-Buchhaltung vs Inhalt-Grounding
fig2, ax2 = plt.subplots(figsize=(8, 5.2))
vals = [summary["exact_recall_pct"] or 0, hidden_success if hidden_success is not None else 0]
ax2.bar([0, 1], vals, color=[C_OK, C_BAD], width=0.55)
ax2.set_xticks([0, 1])
ax2.set_xticklabels(["Zustands-Buchhaltung\n(POST→GET in-context,\ninkl. Update)",
                     "Inhalt-Grounding\n(GET auf verborgene\nvorbestehende Daten)"])
ax2.set_ylabel("Erfolg / exakter Recall (%)"); ax2.set_ylim(0, 105)
for x, v in zip([0, 1], vals):
    ax2.text(x, v + 2, f"{v:.0f}%", ha="center", fontweight="bold", fontsize=15)
ax2.set_title("AgentWorld als Umgebung: was es KANN und was NICHT\n"
              "B merkt sich, was du schreibst — erfindet aber, was es nie sah",
              fontsize=13.5, fontweight="bold", pad=12)
ax2.spines[["top", "right"]].set_visible(False)
fig2.tight_layout()
fig2.savefig(os.path.join(OUTDIR, "track3_state_dissociation.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/track3_state_dissociation.png")
