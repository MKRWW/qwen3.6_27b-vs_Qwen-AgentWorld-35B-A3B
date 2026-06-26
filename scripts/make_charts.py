"""Erzeugt LinkedIn-taugliche Charts aus docs/data/summary.json -> docs/charts/*.png

Aufruf:  python scripts/make_charts.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY = os.path.join(HERE, "docs", "data", "summary.json")
OUTDIR = os.path.join(HERE, "docs", "charts")
os.makedirs(OUTDIR, exist_ok=True)

with open(SUMMARY, encoding="utf-8") as f:
    S = json.load(f)
A, B = S["models"]["A"], S["models"]["B"]

C_A = "#4C72B0"   # Qwen3.6 (generisch) - blau
C_B = "#DD8452"   # AgentWorld (gehypt) - orange
LABELS = ["Qwen3.6-27B\n(generisch)", "AgentWorld-35B\n(World Model)"]
plt.rcParams.update({"font.size": 13})


def err(d):
    """asymmetrische Fehlerbalken aus min/max um mean."""
    return [[d["mean"] - d["min"]], [d["max"] - d["mean"]]]


def bars(ax, vals, errs, colors, title, ylabel, fmt="{:.0f}", ymax=None):
    x = [0, 1]
    b = ax.bar(x, vals, color=colors, width=0.6,
              yerr=errs if errs else None, capsize=8, ecolor="#333", error_kw={"elinewidth": 2})
    ax.set_xticks(x); ax.set_xticklabels(LABELS)
    ax.set_title(title, fontsize=15, fontweight="bold", pad=12)
    ax.set_ylabel(ylabel)
    if ymax:
        ax.set_ylim(0, ymax)
    for xi, v in zip(x, vals):
        ax.text(xi, v, "  " + fmt.format(v), ha="center", va="bottom", fontweight="bold", fontsize=13)
    ax.spines[["top", "right"]].set_visible(False)
    return b


# ---- HERO: 3 Panels (Genauigkeit / Kosten / Zuverlaessigkeit) ----
fig, axes = plt.subplots(1, 3, figsize=(15, 5.2))

# 1) Genauigkeit (neutraler Judge) -> Gleichstand
ja, jb = A["judge_factuality"], B["judge_factuality"]
bars(axes[0], [ja["mean"], jb["mean"]], None,
     [C_A, C_B], "Genauigkeit (neutraler Judge)", "Score 0–100", "{:.1f}", ymax=100)
# Fehlerbalken separat sauber setzen
axes[0].errorbar([0, 1], [ja["mean"], jb["mean"]],
                 yerr=[[ja["mean"]-ja["min"], jb["mean"]-jb["min"]], [ja["max"]-ja["mean"], jb["max"]-jb["mean"]]],
                 fmt="none", ecolor="#333", elinewidth=2, capsize=8)
axes[0].text(0.5, 92, "≈ Gleichstand", ha="center", fontsize=13, style="italic", color="#555")

# 2) Token-Kosten -> ~9x
ta, tb = A["tok_median"], B["tok_median"]
bars(axes[1], [ta["mean"], tb["mean"]], None, [C_A, C_B],
     "Kosten je Vorhersage (Token, Median)", "Completion-Tokens", "{:.0f}", ymax=tb["mean"]*1.2)
fac = tb["mean"]/ta["mean"]
axes[1].annotate(f"≈ {fac:.0f}× teurer", xy=(1, tb["mean"]), xytext=(0.35, tb["mean"]*0.9),
                 fontsize=14, fontweight="bold", color="#B5462F",
                 arrowprops=dict(arrowstyle="->", color="#B5462F", lw=2))

# 3) Zuverlaessigkeit -> leere Antworten (niedriger=besser)
ea, eb = A["empty_per_81"], B["empty_per_81"]
bars(axes[2], [ea["mean"], eb["mean"]], None, [C_A, C_B],
     "Leere Antworten (von 81)", "Anzahl  (weniger = besser)", "{:.1f}", ymax=max(ea["max"], eb["max"], 1)*1.4)
axes[2].text(0.5, max(ea["max"], 1)*1.15, "B liefert\nzuverlässiger", ha="center", fontsize=12, style="italic", color="#555")

fig.suptitle("AgentWorld-35B-A3B vs. Qwen3.6-27B  —  Terminal/SWE-Next-State (N=2 Replikate, echte Ground Truth)",
             fontsize=14, fontweight="bold", y=1.02)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "hero.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/hero.png")

# ---- Punchline: Genauigkeit gleich, Kosten 9x (2 Panels, plakativ) ----
fig2, ax2 = plt.subplots(1, 2, figsize=(11, 5))
bars(ax2[0], [ja["mean"], jb["mean"]], None, [C_A, C_B], "Gleiche Genauigkeit", "Judge-Score", "{:.1f}", ymax=100)
ax2[0].errorbar([0, 1], [ja["mean"], jb["mean"]],
                yerr=[[ja["mean"]-ja["min"], jb["mean"]-jb["min"]], [ja["max"]-ja["mean"], jb["max"]-jb["mean"]]],
                fmt="none", ecolor="#333", elinewidth=2, capsize=8)
bars(ax2[1], [ta["mean"], tb["mean"]], None, [C_A, C_B], f"...aber ≈ {fac:.0f}× die Kosten", "Token/Vorhersage", "{:.0f}", ymax=tb["mean"]*1.2)
fig2.suptitle('"3× besser"?  —  Gleiche Genauigkeit, ~9× die Token.', fontsize=15, fontweight="bold", y=1.0)
fig2.tight_layout()
fig2.savefig(os.path.join(OUTDIR, "accuracy_vs_cost.png"), dpi=150, bbox_inches="tight")
print("-> docs/charts/accuracy_vs_cost.png")
