# FINDINGS (Zwischenstand)

> Status: **Pipeline beider Tracks end-to-end bewiesen, Datensatz noch klein.**
> Vor dem Zitieren von Zahlen **[THREATS.md](THREATS.md) lesen** (int4 vs NVFP4,
> verschiedene GPUs, kleine N → Richtungs-Indikatoren, keine p-Werte).
> Tabellen regenerierbar: `python scripts/make_report.py results/raw`.

## Kernbefund bisher

**Noch kein inhaltlicher Modell-Befund** — beide bestehen die bisherigen Trivial-Tasks.

**Operative Notiz (KEIN Modell-Befund):** AgentWorld (B) brauchte vier
hermes-Workarounds zum Starten (api_key in Config, context_length-Override ×2,
max_tokens-Cap), Qwen3.6 (A) keinen. Ursache ist aber **reine Serving-Asymmetrie**,
nicht das Modell: B wird auf der vast-GPU mit nur **32k** Kontext serviert (VRAM-bound,
NVFP4 auf 1× RTX PRO 5000), A lokal mit **256k / 512k KV-Cache**. Das Model Card von B
behauptet selbst **262k** — die 32k sind eine Hardware-/Config-Entscheidung. Wird B mit
≥64k serviert, verschwinden die Workarounds. → **Nicht** als „Agenten laufen schlechter"
werten; nur als Deployment-Hürde *bei dieser Serving-Config* notieren. Im Benchmark
neutralisiert durch Paritäts-Cap (beide auf 64k/2048, s. THREATS §5c).

## Track 1 — Hype-Test (Policy / Agent), Stand

| Modell | Tasks | Success | hermes-Fehler | Anmerkung |
|--------|-------|---------|---------------|-----------|
| A (Qwen3.6-27b) | 1 | 1/1 | 0 | Fix korrekt (`range(1,n)`→`range(1,n+1)`) |
| B (AgentWorld)  | 1 | 1/1 | 0 | Fix korrekt, +entfernte Bug-Kommentar |

→ Auf dem trivialen Bugfix bestehen **beide**. Ein einzelner einfacher Task
diskriminiert nicht — sagt nichts über die „Code ist besser"-Behauptung. Braucht die
härtere Suite (s.u.).

## Track 2 — World-Model-Fidelity, Stand

| Modell | Triples | Factuality | Format | Judge |
|--------|---------|-----------|--------|-------|
| A (Qwen3.6-27b) | 5 | 43.3 | 100.0 | (aus) |
| B (AgentWorld)  | 5 | 43.3 | 100.0 | (aus) |

→ Auf 5 Trivial-Terminal-Triples **identisch**. Grader noch grob, LLM-Judge noch aus.
Hier *sollte* B glänzen, wenn der Hype einen Kern hat — zeigt sich erst mit härteren
Triples + Grader v2 + Judge.

## Was damit NICHT gezeigt ist
- Ob B bei *schwierigen* Agent-Tasks besser/schlechter ist (Suite zu klein).
- Ob B als World Model wirklich überlegen ist (Track 2 noch nicht ausgereizt).
- Irgendeine Aussage zu Speed (bewusst nicht verglichen, s. THREATS).

## Nächste Schritte für belastbare Zahlen
1. Diskriminierende Task-/Triple-Suite (Fehlerfälle, git/pip/pytest, mehrstufig).
2. Grader v2 + LLM-Judge (Cross-Judging A↔B, optional Claude).
3. `card`-Sampling-Regime gegenlaufen.
