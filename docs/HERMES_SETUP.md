# hermes als Benchmark-Harness — die Recipe (hart erarbeitet)

Wie wir hermes nicht-invasiv und reproduzierbar als Agent-Harness für **beide**
Modelle fahren. Diese Datei dokumentiert, was funktioniert und *warum* — inkl. der
Stolpersteine, die AgentWorld (B) verursacht hat.

## Invocation (funktioniert für A und B)

```bash
HERMES_HOME=<isoliertes-bench-home> \
OPENAI_API_KEY=<key> \
HERMES_INFERENCE_MODEL=<model_id> \
hermes -z "<prompt>" --yolo --cli      # cwd = Task-Sandbox
```

- `HERMES_HOME` → isoliertes Home (eigenes `config.yaml`); **die echte
  `~/.hermes`-Config bleibt unangetastet**. Verifiziert über `hermes_constants.py`.
- `-z` = One-Shot-Prompt (kein `run`-Subcommand! häufiger Irrtum).
- `--yolo` = Tool-Calls auto-bestätigen (headless). `--cli` = kein TUI.
- `HERMES_INFERENCE_MODEL` setzt das Modell, **ohne** `-m provider/model`-Parsing
  auszulösen (s.u.).

## config.yaml im Bench-Home

```yaml
model:
  default: "<model_id>"          # bei B mit Slash: lovedheart/Qwen-AgentWorld-35B-A3B-NVFP4
  provider: custom               # OpenAI-kompatibler Endpoint
  base_url: <endpoint>/v1
  api_key: "<key>"               # PFLICHT in der Config (s. Stolperstein 2)
  context_length: 64000          # Override (s. Stolperstein 3)
  max_tokens: 2048               # Output-Cap (s. Stolperstein 4)
toolsets:
- hermes-cli                     # Standard-Bundle: Shell + Datei-Editing
agent:
  max_turns: 30
auxiliary:
  compression:
    context_length: 64000        # zweite Override-Stelle (s. Stolperstein 3)
```

## Stolpersteine (alle bei B aufgetreten, A „lief einfach")

1. **`-m lovedheart/...` → „No LLM provider configured".**
   hermes liest `provider/model`-Syntax; der Slash im HF-Repo-Namen macht
   `lovedheart` zum (unbekannten) Provider. **Fix:** Modell via
   `HERMES_INFERENCE_MODEL` + config-`default` setzen, **nicht** per `-m`.

2. **401 AuthenticationError.** `HERMES_API_KEY`/`HERMES_BASE_URL` greifen nur im
   tui_gateway-Pfad, nicht im CLI-Agent. Der custom-Provider hat keinen festen
   Env-Key. **Fix:** `api_key` direkt in `config.yaml` (+ `OPENAI_API_KEY` als
   Fallback). Bei A unsichtbar, weil das lokale vLLM jeden Key akzeptiert.

3. **„context window 32,000 below minimum 64,000".** hermes verlangt ≥64k Kontext,
   B serviert nur 32k. Greift an **zwei** Stellen: Haupt- *und*
   Auxiliary-Compression-Modell. **Fix:** beide `context_length: 64000`.

4. **„agent failed: 'final_response'".** Mit context_length=64000 setzt hermes
   `max_tokens=65536` — größer als B's reales 32k-Fenster → kaputte Completion →
   kein final_response. **Fix:** `model.max_tokens: 2048` (Output-Cap, damit
   Requests in B's 32k passen).

## Was das für den Hype-Test bedeutet

A (Qwen3.6, 262k Kontext) lief ohne jeden Workaround. B (AgentWorld) brauchte vier
Eingriffe, im Kern weil **sein 32k-Serving-Kontext unter hermes' 64k-Betriebs-Floor
liegt**. Das ist reale Friktion gegen die Behauptung „alle Agenten laufen besser" —
und gehört als qualitatives Finding in [FINDINGS.md](FINDINGS.md) (nicht in eine
Erfolgs-/Fehler-Zahl, da via Override umgehbar).

> Hinweis: `context_length: 64000` ist eine *Notlüge* an hermes. Solange ein Task
> real unter 32k bleibt (unsere Tasks: ~10k), funktioniert es. Größere Kontexte
> würde B mit HTTP 400 ablehnen — dann zählt das als Task-Limit/Fehler.

## Parität (Fairness)

A und B laufen mit **identischen** Agent-Settings (context_length 64000, max_tokens
2048, max_turns 30, toolset hermes-cli). Die 32k-Beschränkung von B setzt die Decke;
wir wenden dieselbe Decke auf A an, damit der Loop fair vergleichbar ist.

## Oracle-Umgebung

pytest läuft in dedizierter venv `~/.cache/awbench-venv` (entkoppelt vom
System-Python). Vom Runner automatisch angelegt (`ensure_bench_venv()`).
