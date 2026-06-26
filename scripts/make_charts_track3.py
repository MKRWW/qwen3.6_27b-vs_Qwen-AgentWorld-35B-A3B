"""LinkedIn-taugliche Track-3-Charts aus den beiden Summaries -> docs/charts/.

  track3_success.png         : Kurzhorizont (closedloop) real vs sim + Getaeuscht.
  track3_divergence.png      : Kurzhorizont Divergenz/Schritt.
  track3_lh_success.png      : Langhorizont (brutal) real vs sim + Getaeuscht.
  track3_compare.png         : HEADLINE — kurz vs lang fuer sim-Erfolg / Getaeuscht /
                               Divergenz. Die ganze Geschichte in einem Bild.

Aufruf:  python scripts/make_charts_track3.py
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "docs", "data")
OUTDIR = os.path.join(HERE, "docs", "charts")
os.makedirs(OUTDIR, exist_ok=True)

C_REAL = "#4C72B0"   # echte Umgebung / kurz - blau
C_SIM = "#DD8452"    # simulierte Umgebung / lang - orange
C_WARN = "#B5462F"
plt.rcParams.update({"font.size": 13})


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def err1(d):
    if not d:
        return [[0], [0]]
    return [[max(0, d["mean"] - d["min"])], [max(0, d["max"] - d["mean"])]]


def three_bar(S, title, fname):
    real = S["real_success_pct"] or {"mean": 0, "min": 0, "max": 0}
    sim = S["sim_replay_success_pct"] or {"mean": 0, "min": 0, "max": 0}
    dec = S["sim_deceived_pct"] or {"mean": 0, "min": 0, "max": 0}
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    x = [0, 1, 2]
    vals = [real["mean"], sim["mean"], dec["mean"]]
    ax.bar(x, vals, color=[C_REAL, C_SIM, C_WARN], width=0.62)
    ax.errorbar(x, vals,
                yerr=[[err1(real)[0][0], err1(sim)[0][0], err1(dec)[0][0]],
                      [err1(real)[1][0], err1(sim)[1][0], err1(dec)[1][0]]],
                fmt="none", ecolor="#333", elinewidth=2, capsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(["A @ real\n(Baseline)", "A @ sim\n(Real-Replay)",
                        "Getäuscht\n(DONE, real fail)"])
    ax.set_ylabel("Anteil der Tasks (%)")
    ax.set_ylim(0, 105)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontweight="bold", fontsize=14)
    ax.set_title(title, fontsize=15, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, fname), dpi=150, bbox_inches="tight")
    print(f"-> docs/charts/{fname}")


def divergence_bar(S, title, fname):
    div = S["divergence_per_step_pct"] or {"mean": 0, "min": 0, "max": 0}
    fig, ax = plt.subplots(figsize=(7, 5.2))
    ax.bar([0], [div["mean"]], color=C_SIM, width=0.5)
    ax.errorbar([0], [div["mean"]], yerr=err1(div), fmt="none", ecolor="#333", elinewidth=2, capsize=8)
    ax.set_xticks([0]); ax.set_xticklabels(["sim-Observation ≠ real-Observation"])
    ax.set_ylabel("Anteil der Schritte (%)"); ax.set_ylim(0, 105)
    ax.text(0, div["mean"] + 1.5, f"{div['mean']:.0f}%", ha="center", va="bottom",
            fontweight="bold", fontsize=14)
    ax.set_title(title + f"\n(gepoolt {S.get('divergence_pooled_pct')} %, n={S.get('n_steps_compared')})",
                 fontsize=14, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, fname), dpi=150, bbox_inches="tight")
    print(f"-> docs/charts/{fname}")


def compare(short, lon):
    """HEADLINE: kurz vs lang fuer sim-Erfolg / Getaeuscht / Divergenz."""
    metrics = [
        ("Erfolg A@sim\n(Real-Replay)", "sim_replay_success_pct"),
        ("Getäuscht-Rate", "sim_deceived_pct"),
        ("Divergenz / Schritt", "divergence_per_step_pct"),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    import numpy as np
    xs = np.arange(len(metrics))
    w = 0.36
    sv = [(short[k] or {"mean": 0})["mean"] for _, k in metrics]
    lv = [(lon[k] or {"mean": 0})["mean"] for _, k in metrics]
    se = [[max(0, (short[k] or {"mean":0,"min":0})["mean"]-(short[k] or {"min":0})["min"]) for _,k in metrics],
          [max(0, (short[k] or {"mean":0,"max":0})["max"]-(short[k] or {"mean":0})["mean"]) for _,k in metrics]]
    le = [[max(0, (lon[k] or {"mean":0,"min":0})["mean"]-(lon[k] or {"min":0})["min"]) for _,k in metrics],
          [max(0, (lon[k] or {"mean":0,"max":0})["max"]-(lon[k] or {"mean":0})["mean"]) for _,k in metrics]]
    b1 = ax.bar(xs - w/2, sv, w, color=C_REAL, label="kurz (8 Tasks, agnostisch lösbar)")
    b2 = ax.bar(xs + w/2, lv, w, color=C_WARN, label="lang/brutal (6 Tasks, Inhalt erzwungen)")
    ax.errorbar(xs - w/2, sv, yerr=se, fmt="none", ecolor="#333", elinewidth=1.8, capsize=6)
    ax.errorbar(xs + w/2, lv, yerr=le, fmt="none", ecolor="#333", elinewidth=1.8, capsize=6)
    for b in list(b1) + list(b2):
        h = b.get_height()
        ax.text(b.get_x() + b.get_width()/2, h + 1.5, f"{h:.0f}%", ha="center",
                va="bottom", fontweight="bold", fontsize=12)
    ax.set_xticks(xs); ax.set_xticklabels([m for m, _ in metrics])
    ax.set_ylabel("Prozent"); ax.set_ylim(0, 105)
    ax.set_title("Closed-Loop gegen AgentWorld: hält der Agent — oder nicht?\n"
                 "Es hängt davon ab, ob die Aufgabe den simulierten Inhalt ERZWINGT",
                 fontsize=14, fontweight="bold", pad=12)
    ax.legend(loc="upper center", frameon=False, fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTDIR, "track3_compare.png"), dpi=150, bbox_inches="tight")
    print("-> docs/charts/track3_compare.png")


short = load("track3_summary.json")
three_bar(short, "Closed-Loop (kurze Tasks): löst der Agent die Aufgabe\nin AgentWorld als Umgebung?", "track3_success.png")
divergence_bar(short, "Per-Step-Divergenz (kurze Tasks)", "track3_divergence.png")
try:
    lon = load("track3_longhorizon_summary.json")
    three_bar(lon, "Langhorizont-BRUTAL: Agent muss simulierten Inhalt konsumieren", "track3_lh_success.png")
    divergence_bar(lon, "Per-Step-Divergenz (Langhorizont, brutal)", "track3_lh_divergence.png")
    compare(short, lon)
except FileNotFoundError:
    print("(longhorizon-Summary fehlt -> nur Kurzhorizont-Charts)")
