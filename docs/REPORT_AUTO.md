# FINDINGS — AgentWorld-35B-A3B vs Qwen3.6-27b

> Auto-generiert von scripts/make_report.py. **Vor dem Zitieren docs/THREATS.md + FINDINGS.md lesen** (int4 vs NVFP4, nur Terminal, N=26, Ceiling-Effekt).

## Track 1 — Hype-Test (Policy / Agent)

| Modell | Regime | Tasks | Success-Rate | hermes-Fehler |
|--------|--------|-------|--------------|---------------|
| A | greedy | 3 | 3/3 | 0 |
| B | greedy | 3 | 3/3 | 0 |

## Track 2 — World-Model-Fidelity

| Modell | Regime | Triples | Factuality | Format | tok(median) | Consist.* |
|--------|--------|---------|-----------|--------|-------------|-----------|
| A | card | 81 | 77.8 | 96.3 | 178 | 96.3 |
| A | card | 81 | 76.9 | 95.1 | 173 | 93.8 |
| B | card | 81 | 77.8 | 100.0 | 362 | 100.0 |
| B | card | 81 | 81.1 | 98.8 | 450 | 98.8 |

*Realism/Quality des LLM-Judge sind hier nicht vertrauenswürdig (unkalibrierte Cross-Judges) — siehe FINDINGS.md. tok = completion_tokens (Effizienz, fair vergleichbar).

## Interpretation

- Hält Hypothese 1 (AgentWorld schwächer als Policy)?  → siehe Track-1-Tabelle.
- Hält Hypothese 2 (AgentWorld stärker als World Model)? → siehe Track-2-Tabelle.
- Erinnerung: kleine Stichprobe, Richtungs-Indikator, kein p-Wert.
