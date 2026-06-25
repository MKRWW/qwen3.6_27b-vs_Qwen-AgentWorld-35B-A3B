# Methodik

Ziel: ein **reproduzierbarer** Vergleich zweier OpenAI-kompatibler Endpoints unter
zwei Aufgaben-Brillen. Jeder hier dokumentierte Parameter ist im Code gepinnt und
landet im Run-Header jeder JSONL-Datei.

## 0. Modelle unter Test

| Kürzel | `model`-id (vom Endpoint) | Endpoint | Sampling-Default |
|--------|---------------------------|----------|------------------|
| A | `qwen3.6-27b` | `http://192.168.178.21:8000/v1` | greedy + Card-Settings |
| B | `<von probe_endpoints.sh>` | `http://194.228.55.129:37773/v1` | greedy + Card-Settings |

Die `model`-id von B wird beim ersten `probe_endpoints.sh`-Lauf ausgelesen und in
`config/models.yaml` eingetragen (Platzhalter bis dahin).

## 1. Sampling-Regime

Beide Modelle laufen in **zwei** Konfigurationen, getrennt berichtet:

| Regime | temperature | top_p | top_k | seed | Zweck |
|--------|-------------|-------|-------|------|-------|
| `greedy` | 0.0 | 1.0 | — | 7 | Determinismus, Repro-Anker |
| `card`   | 0.6 | 0.95 | 20 | 7 | Empfohlene Settings der Model Card |

`max_tokens`: **≥ 1024** für Reasoning-Modelle. Hintergrund (aus dem Setup-Hinweis):
bei zu kleinem `max_tokens` verbraucht das Reasoning-Modell das Budget im Denk-Teil
und liefert **leeren** `content` zurück. Wir setzen Track-spezifische Limits (s.u.)
und loggen `finish_reason`, um abgeschnittene Antworten zu erkennen.

> Determinismus-Vorbehalt: vLLM ist bei temp=0 *weitgehend*, aber nicht garantiert
> bit-genau reproduzierbar (Batching/Kernels). Wir behandeln `greedy` als
> Stabilitäts-Anker, nicht als Bit-Garantie.

## 2. Track 1 — Hype-Test (Policy / Agent)

**Frage:** Löst das Modell als hermes-Backend echte Agent-Tasks?

**Harness:** hermes (`v0.17.0`, WSL) wird über `OPENAI_BASE_URL` / `OPENAI_API_KEY` /
Modell-id auf A bzw. B gezeigt. Identische Tasks, identisches System-Prompt-Setup,
identische Tool-Definitionen.

**Tasks:** `tasks/swe/` (Bugfix in Mini-Repo, **pytest-Oracle**) und
`tasks/terminal/` (Befehlsfolge, Oracle prüft FS-Zustand bzw. stdout).

**Metriken (alle automatisch):**
| Metrik | Definition |
|--------|-----------|
| `success` | Oracle besteht (pytest grün / erwarteter Endzustand) |
| `tool_call_valid_rate` | Anteil syntaktisch & semantisch gültiger Tool-Calls (JSON parsebar, Tool existiert, Args-Schema erfüllt) |
| `turns_to_done` | Agent-Schritte bis Erfolg/Abbruch |
| `tokens_in/out` | Summe über alle Turns |
| `wall_clock_s` | Ende-zu-Ende-Zeit (Latenz-Vorbehalt: B ist Remote) |
| `crash_reason` | bei Abbruch: malformed-tool-call / loop / timeout / empty-content |

`max_tokens` Track 1: **2048** pro Turn.

## 3. Track 2 — World-Model-Fidelity

**Frage:** Sagt das Modell den nächsten Umgebungs-Zustand korrekt voraus?

**Ground-truth-Erzeugung:** In einer **WSL-Sandbox** (frisches tmp-Verzeichnis,
fixierte Tool-Versionen) wird eine reale Aktions-Sequenz ausgeführt und jeder
Schritt aufgezeichnet als Triple:

```
{ history: [...vorherige (action, observation)],
  action:  "<nächster Befehl/Tool-Call>",
  truth:   { stdout, stderr, exit_code, fs_delta } }
```

Das Modell bekommt `history + action` (über das domänen-spezifische System-Prompt
der Card) und muss `next_state` vorhersagen. Verglichen wird Vorhersage vs. `truth`.

**Scoring (AgentWorldBench-Stil), pro Triple 0–100:**
| Dimension | Wie gemessen | Automatisierung |
|-----------|--------------|-----------------|
| **Format** | Valide Struktur (z. B. erwartete Felder/Markup) | deterministisch (Regex/Schema) |
| **Factuality** | exit_code-Match, stdout-Schlüsselfakten, File-Existenz/-Inhalt | deterministisch (exakt + fuzzy) |
| **Consistency** | kein Widerspruch zum `history` | LLM-Judge |
| **Realism** | plausibel als echte Ausgabe (Format von Pfaden, Fehlermeldungen, Timestamps) | LLM-Judge |
| **Quality** | Vollständigkeit & Nützlichkeit | LLM-Judge |

**LLM-Judge:** fixer Prompt (`harness/graders.py`), temp=0, ein neutrales Modell
(Default: Qwen3.6 als lokaler Judge; optional Claude für Gegenprobe). Der Judge
sieht `truth` und `prediction` und vergibt pro Dimension einen Score + Begründung.
Judge-Wahl wird im Run-Header geloggt; **Self-Judging wird vermieden** (Modell B
wird nie von B gejudged).

`max_tokens` Track 2: **1024** für die Vorhersage.

## 4. Datensatz-Größe (Start)

- Track 1: 8–12 Tasks (SWE + Terminal gemischt), je 1 Run pro (Modell × Regime).
- Track 2: 30–50 Triples, je 1 Run pro (Modell × Regime).

Klein genug für schnelle Iteration, groß genug um grobe Effekte zu sehen. **Keine
statistische Signifikanz** bei dieser Größe — Befunde sind Richtungs-Indikatoren,
nicht p-Werte. Das steht auch in FINDINGS.md.

## 5. Run-Header (in jeder JSONL-Datei, erste Zeile)

```json
{ "type": "run_header", "track": 1, "model": "A", "model_id": "qwen3.6-27b",
  "endpoint": "http://192.168.178.21:8000/v1", "regime": "greedy",
  "sampling": {"temperature": 0.0, "top_p": 1.0, "seed": 7},
  "repo_git_sha": "<sha>", "started_at_utc": "<iso>", "harness_version": "0.1.0" }
```

## 6. Was wir NICHT behaupten

- Keine Aussage über andere Quant-Stufen / Hardware als die hier getestete.
- Keine Aussage über die 5 nicht getesteten Domänen (MCP/Search/Android/Web/OS).
- Latenz-Zahlen sind **nicht** modell-fair (LAN vs vast.ai). Siehe THREATS.md.
