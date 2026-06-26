"""LinkedIn-taugliche Track-3-Charts aus docs/data/track3_summary.json -> docs/charts/.

  track3_success.png : A@real vs A@sim (Real-Replay) Erfolgsrate + Getaeuscht-Rate.
  track3_divergence.png : Divergenz/Schritt (Per-Step-Fidelity-Bruch im Closed-Loop).

Aufruf:  python scripts/make_charts_track3.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY = os.path.join(HERE, "docs", "data", "track3_summary.json")
OUTDIR = os.path.join(HERE, "docs", "charts")
os.makedirs(OUTDIR, exist_ok=True)

with open(SUMMARY, encoding="utf-8") as f:
    S = json.load(f)

C_REAL = "#4C72B0"   # echte Umgebung - blau
C_SIM = "#DD8452"    # simulierte Umgebung (AgentWorld) - orange
C_WARN = "#B5462F"
plt.rcParams.update({"font.size": 13})


def err(d):
    if not d:
        return [[0], [0]]
    return [[max(0, d["mean"] - d["min"])], [max(0, d["max"] - d["mean"])]]


# ---- Chart 1: Erfolgsrate real vs sim + Getaeuscht ----
real = S["real_success_pct"] or {"mean": 0, "min": 0, "max": 0}
sim = S["sim_replay_success_pct"] or {"mean": 0, "min": 0, "max": 0}
dec = S["sim_deceived_pct"] or {"mean": 0, "min": 0, "max": 0}

fig, ax = plt.subplots(figsize=(8.5, 5.4))
x = [0, 1, 2]
vals = [real["mean"], sim["mean"], dec["mean"]]
colors = [C_REAL, C_SIM, C_WARN]
labels = ["A @ real\n(Baseline)", "A @ sim\n(Real-Replay)", "Getäuscht\n(DONE, real fail)"]
ax.bar(x, vals, color=colors, width=0.62)
ax.errorbar(x, vals,
            yerr=[[err(real)[0][0], err(sim)[0][0], err(dec)[0][0]],
                  [err(real)[1][0], err(sim)[1][0], err(dec)[1][0]]],
            fmt="none", ecolor="#333", elinewidth=2, capsize=8)
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylabel("Anteil der Tasks (%)")
ax.set_ylim(0, 105)
for xi, v in zip(x, vals):
    ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontweight="bold", fontsize=14)
ax.set_title("Closed-Loop: löst der Agent die Aufgabe,\nwenn AgentWorld die Umgebung ist?",
             fontsize=15, fontweight="bold", pad=12)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "track3_success.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/track3_success.png")

# ---- Chart 2: Divergenz/Schritt ----
div = S["divergence_per_step_pct"] or {"mean": 0, "min": 0, "max": 0}
fig2, ax2 = plt.subplots(figsize=(7, 5.2))
ax2.bar([0], [div["mean"]], color=C_SIM, width=0.5)
ax2.errorbar([0], [div["mean"]], yerr=err(div), fmt="none", ecolor="#333", elinewidth=2, capsize=8)
ax2.set_xticks([0]); ax2.set_xticklabels(["sim-Observation ≠ real-Observation"])
ax2.set_ylabel("Anteil der Schritte (%)")
ax2.set_ylim(0, max(100, div["max"] * 1.3 if div else 100))
ax2.text(0, div["mean"] + 1.5, f"{div['mean']:.0f}%", ha="center", va="bottom",
         fontweight="bold", fontsize=14)
ax2.set_title(f"Per-Step-Divergenz im Closed-Loop\n(gepoolt {S.get('divergence_pooled_pct')} %, "
              f"n={S.get('n_steps_compared')} Schritte)", fontsize=14, fontweight="bold", pad=12)
ax2.spines[["top", "right"]].set_visible(False)
fig2.tight_layout()
fig2.savefig(os.path.join(OUTDIR, "track3_divergence.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/track3_divergence.png")
