# FINDINGS

_Noch keine Runs. Diese Datei wird von `scripts/make_report.py` aus
`results/raw/*.jsonl` regeneriert, sobald die Benchmarks gelaufen sind._

```bash
python scripts/make_report.py results/raw > docs/FINDINGS.md
```

**Vor dem Zitieren von Zahlen:** [docs/THREATS.md](THREATS.md) lesen.
Kurzfassung der Vorbehalte: int4 (A) vs bf16 (B), 27B vs 35B-A3B, LAN vs
vast.ai-Latenz, kleine Stichprobe → Richtungs-Indikatoren, keine p-Werte.

## Erwartete Hypothesen (vor den Runs festgehalten)

1. **Track 1 (Policy):** AgentWorld ≤ Qwen3.6 — es ist kein Policy-Modell.
2. **Track 2 (World Model):** AgentWorld ≥ Qwen3.6 — dafür gebaut.

Wenn beides hält → der LinkedIn-Hype misst das Modell an der falschen Aufgabe.
