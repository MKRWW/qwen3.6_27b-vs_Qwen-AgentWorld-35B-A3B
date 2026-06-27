# Track 3 — Closed-Loop: Agent läuft gegen AgentWorld als Umgebung

**Auslöser:** ein Kommentar zum Artikel. Kernpunkt (korrekt):
AgentWorld ist faktisch eine **flexible Mock-API** für Agenten-Umgebungen. Die
*eigentliche* Nutzung ist nicht „Agent löst Tasks" (Track 1, falsche Nutzung) und
auch nicht nur „Single-Step-Vorhersage" (Track 2) — sondern: **ein echter Agent läuft
nicht gegen echte Tools, sondern gegen das Modell als Umgebung.** Das haben wir noch
nicht getestet. Track 3 holt das nach.

## Die offene Frage
Track 2 zeigte ~84 % Per-Step-Fidelity. **Reicht das, damit ein echter Agent eine
ganze Aufgabe gegen die *simulierte* Umgebung löst?** Hypothese: nein bzw. deutlich
schlechter — weil sich Per-Step-Fehler über die Rollout-Länge **aufschaukeln** (84 %^N).
Und: wie oft wird der Agent **getäuscht** (glaubt Erfolg, real gescheitert)?

## Design (minimaler ReAct-Loop, EIGENER Code — kein hermes-Hack, kontrollierbarer)
- **Policy** = Qwen3.6-27B (Modell A) — entscheidet den nächsten Shell-Befehl.
- **Environment** = austauschbar:
  - `real`: echter WSL-Sandbox-Shell (Baseline/Kontrolle).
  - `sim`: AgentWorld (Modell B) sagt die Observation voraus — exakt das Track-2-Setup
    (offizieller Domänen-Prompt `config/prompts/terminal/system_prompt.txt`,
    Format `Action: execute_bash\nCommand: …`, thinking AN, max_tokens ~16k).
- Loop: Policy → Befehl → Environment → Observation → zurück in den Verlauf,
  bis Policy `DONE` sagt oder `max_steps` (z. B. 12).

## Bedingungen & Metriken (3 Sichten pro Task)
1. **A@real** (Baseline): löst der Agent mit *perfekter* Umgebung? → Oracle-Erfolg.
2. **A@sim** (Treatment): derselbe Agent, Umgebung = AgentWorld:
   - **Real-Replay-Erfolg:** die vom Agenten in `sim` erzeugte Befehlssequenz wird in
     einer **frischen echten Sandbox nachgespielt** → Oracle. (Hat der Agent real
     gelöst, obwohl er gegen die Simulation lief?)
   - **Getäuscht-Rate:** Agent sagt `DONE`/glaubt Erfolg, aber Real-Replay scheitert.
   - **Divergenz/Schritt:** sim-Observation ≠ real-Observation an Schritt k (macht das
     Aufschaukeln sichtbar; misst man, indem man jeden sim-Befehl parallel real ausführt).

**Headline-Frage:** Erfolgsrate A@sim (real-replay) vs. A@real — wie stark bricht sie
ein, wenn die Umgebung simuliert ist? Plus Getäuscht-Rate.

## Tasks
6–8 **shell-lösbare** Multi-Step-Tasks mit deterministischem `oracle.sh`. Beispiele:
Datei erzeugen/bearbeiten/prüfen, kleine Pipeline, mehrstufige git-/text-Operationen.
Neu unter `tasks/closedloop/<name>/` (task.json mit Ziel-Prompt, optional workspace/,
oracle.sh). **Wichtig (Fallstrick):** keine Abhängigkeit von absoluten/zufälligen
Pfaden (`pwd` im random tmp-Root kann das Sim-Modell nicht kennen → triviale Divergenz).
Relative Pfade, deterministische Inhalte.

## Bauteile (neu zu bauen)
- `harness/run_track3_closedloop.py`:
  - ReAct-Loop, Policy-Prompt („Löse die Aufgabe per Shell. Antworte je Schritt mit
    `CMD: <befehl>` oder `DONE`."), beide Environments, Real-Replay-Grading, volle
    Trajektorien-Logs (JSONL), Aggregation (Erfolgsraten + Getäuscht + Divergenz).
  - Sim-Env nutzt `predict()`-Logik aus `run_track2_worldmodel.py` (Modell B, offizielles
    Setup); Observation aus dem vorhergesagten Terminal-Screen extrahieren.
  - Real-Env + Replay nutzen das WSL-persistente-Session-Muster aus `scripts/gen_triples.py`.
- `scripts/seqs/`-Analogon entfällt — Tasks sind agenten-gelöst, nicht vorgegebene Sequenzen.

## Reuse / Fallstricke (aus Track 1+2 hart erkämpft — NICHT neu entdecken)
- **Modell-Clients:** `harness/client.py` → `make_client(model, regime, recorder)`;
  `get_model("A"|"B")` aus `config/models.yaml`; Keys aus `.env` (lädt `client.load_dotenv()`).
- **Norton-SSL-Fix** ist drin (`SSLKEYLOGFILE` wird beim Import gepoppt) — nicht entfernen.
- **B braucht thinking AN + großes Budget** (≤8k → leere Ausgabe; ~16k ok). Empty-Guard
  beachten: leere Vorhersage = Fehlschritt, nicht halluziniert bewerten.
- **A (Policy) kann sich auch verdenken** → im Loop Empty/Timeout abfangen, ggf. Schritt
  als Fehlschlag werten oder 1× retry.
- **OpenRouter-Judge (mistral)** wird für Track 3 i. d. R. NICHT gebraucht (oracle-basiert).
- **Fairness:** identischer Policy-Prompt/Settings in beiden Bedingungen; NUR das
  Environment unterscheidet sich. Pro Bedingung ≥2 Replikate (temp 0.6 Varianz).
- **Prozess-Hygiene:** lange Läufe als Hintergrund; bei Abbruch Prozessbaum killen
  (TaskStop killt den bash-Loop nicht zuverlässig → zusätzlich python/bash per PID killen).
  PC am Standby hindern (rep starb 2× extern).

## Erwartetes Ergebnis (Hypothese, vor dem Lauf festhalten)
A@real löst die meisten Tasks. A@sim bricht **deutlich** ein (Aufschaukeln) und/oder
hohe Getäuscht-Rate. → Pointe: „Per-Step ~84 % klingt gut, aber als Live-Umgebung für
einen Agenten reicht es (noch) nicht." Falls A@sim *doch* hoch ist → starker Pro-Punkt
für AgentWorld. Beides ist ein gutes, ehrliches Artikel-Update (Track 3).
