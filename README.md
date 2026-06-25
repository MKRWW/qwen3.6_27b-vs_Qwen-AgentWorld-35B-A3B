# AgentWorld-35B-A3B vs. Qwen3.6-27b — ein nachvollziehbarer Benchmark

> Wir prüfen, ob die Claims rund um **Qwen-AgentWorld-35B-A3B** ("alle Agenten
> laufen besser, der Code ist besser, alles 3× besser") der Realität standhalten —
> reproduzierbar, mit Code, Logs und ehrlicher Methodik.

## Die These

Laut [Model Card](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) ist
AgentWorld **kein Policy-/Agenten-Modell**, sondern ein **World Model**:

```
Input:  (Umgebungs-Zustand + Verlauf) + geplante Agenten-Aktion
Output: vorhergesagter nächster Umgebungs-Zustand (Observation)
```

Es **entscheidet nicht**, welche Aktion zu tun ist — es **simuliert**, was die
Umgebung *zurückgibt*. Der LinkedIn-Hype behandelt es dagegen wie ein besseres
Coding-/Agenten-Brain. Das ist ein Kategorie-Fehler. Dieser Benchmark testet
**beide Lesarten** und zeigt, wo das Modell tatsächlich gewinnt und wo nicht.

## Zwei Tracks

| Track | Frage | Erwartung |
|-------|-------|-----------|
| **1 — Hype-Test** (Policy) | Ist AgentWorld als hermes-Backend ein besserer Agent als Qwen3.6 auf echten SWE-/Terminal-Tasks? | AgentWorld **verliert** (es ist kein Policy-Modell) |
| **2 — World-Model-Fidelity** | Sagt AgentWorld den nächsten Umgebungs-Zustand treuer voraus als Qwen3.6? | AgentWorld **gewinnt** (dafür gebaut) |

Wenn beide Hypothesen halten, ist die Schlagzeile: *der Hype misst das Modell an
der falschen Aufgabe.*

## Modelle "as deployed" (eure echte Infra)

| Kürzel | Modell | Endpoint | Quant | Hinweis |
|--------|--------|----------|-------|---------|
| **A** | Qwen3.6-27b | `192.168.178.21:8000/v1` (LAN, 2× RTX 3090) | int4 (AutoRound) | `id=qwen3.6-27b`, Tool-Parser aktiv, ctx 262k |
| **B** | AgentWorld-35B-A3B | `194.228.55.129:37773/v1` (vast.ai, 1× RTX PRO 5000) | NVFP4 | MoE 3B aktiv, **Tool-Parser aktiv (verifiziert)**, ctx 32k |

> ⚠️ **Das ist kein cleaner Apples-to-Apples-Vergleich** (int4 vs NVFP4, 27B dense
> vs 35B-A3B MoE, unterschiedlicher Zweck). Wir vergleichen bewusst **"wie es bei
> euch wirklich läuft"** und dokumentieren jede Verzerrung offen in
> [docs/THREATS.md](docs/THREATS.md). Lies das, bevor du Zahlen zitierst.
>
> **Latenz/Speed ist KEINE Vergleichsmetrik** — verschiedene GPUs, LAN vs Remote.
> Wall-clock wird nur informativ geloggt, nie als Modell-Qualität gewertet.
> Beide Prompts werden auf **32k Kontext** gecappt (B's Serving-Limit).

## Schnellstart

```bash
cp .env.example .env        # Endpoints + AgentWorld-Token eintragen
./scripts/probe_endpoints.sh   # Connectivity + Served-Model + Tool-Parser prüfen
# Track 1 (Policy / hermes):
python harness/run_track1_policy.py  --models A,B --tasks tasks/
# Track 2 (World Model):
python harness/run_track2_worldmodel.py --models A,B --tasks tasks/
# Report (Auto-Tabellen; docs/FINDINGS.md ist kuratiert):
python scripts/make_report.py results/raw
```

## Repo-Struktur

```
config/models.yaml          Endpoints, Sampling-Settings, Modell-Kürzel
.env.example                Secrets-Vorlage (Token NICHT committen)
scripts/probe_endpoints.sh  Connectivity + vLLM-Config-Probe
scripts/make_report.py      Aggregiert results/ -> Markdown/CSV
harness/client.py           Dünner OpenAI-Client (Retry, Timeout, volles Logging)
harness/record.py           JSONL-Logging jedes Requests/Responses (Repro)
harness/graders.py          Deterministische + LLM-Judge-Grader
harness/run_track1_policy.py     Track 1 Runner
harness/run_track2_worldmodel.py Track 2 Runner
tasks/terminal/             Terminal-Tasks + Oracles
tasks/swe/                  Mini-Repos + pytest-Oracles
results/                    JSONL-Runs + Scores (raw gitignored, Summaries committed)
docs/METHODOLOGY.md         Exaktes Protokoll, Sampling, Seeds, Fairness
docs/THREATS.md             Threats to Validity
docs/FINDINGS.md            Ergebnisse (nach den Runs gefüllt)
```

## Reproduzierbarkeit

- Jeder Request **und** jede Response landet als JSONL in `results/raw/`.
- Sampling ist gepinnt: primär **greedy (temp=0)**; zusätzlich die Card-Settings
  (temp 0.6 / top_p 0.95 / top_k 20). Beides wird separat berichtet.
- Jeder Run-Header enthält Endpoint, Modell-`id`, Sampling, Seed und den git-SHA
  dieses Repos.
- Siehe [docs/METHODOLOGY.md](docs/METHODOLOGY.md) für das volle Protokoll.

## Lizenz

Code: MIT (siehe `LICENSE`). Die getesteten Modelle haben eigene Lizenzen
(Qwen3.6 / AgentWorld: Apache 2.0).
