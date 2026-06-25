# FINDINGS (Zwischenstand)

> Status: **Pipeline beider Tracks end-to-end bewiesen, Datensatz noch klein.**
> Vor dem Zitieren von Zahlen **[THREATS.md](THREATS.md) lesen** (int4 vs NVFP4,
> verschiedene GPUs, kleine N → Richtungs-Indikatoren, keine p-Werte).
> Tabellen regenerierbar: `python scripts/make_report.py results/raw`.

## Kernbefund bisher (qualitativ, robust)

**Der Hype „alle Agenten laufen besser" hält der Praxis nicht stand — schon beim
Aufsetzen.** Qwen3.6 (A) lief im Agent-Harness hermes **ohne jeden Eingriff**.
AgentWorld (B) brauchte **vier** Workarounds, im Kern weil sein **32k-Serving-Kontext
unter hermes' 64k-Betriebs-Floor** liegt (Details: [HERMES_SETUP.md](HERMES_SETUP.md)):
api_key zwingend in Config, context_length-Override an zwei Stellen, Output-Cap auf
2048. Ohne diese läuft B in hermes gar nicht. Das ist reale Friktion, kein 3×-Boost.

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
