# Status / Lab-Notebook

Chronologisch, was gemacht & gelernt wurde. (Doku-Pflicht: nachvollziehbar.)

## 2026-06-25 — Setup + erster Smoke-Test (Track 2)

### Infrastruktur verifiziert
- **A = Qwen3.6-27b** @ `192.168.178.21:8000` (LAN, 2× RTX 3090, int4) — erreichbar,
  `id=qwen3.6-27b`, ctx 262k, Tool-Parser aktiv.
- **B = AgentWorld-35B-A3B** @ `194.228.55.129:37773` (vast.ai, 1× RTX PRO 5000,
  **NVFP4**) — `id=lovedheart/Qwen-AgentWorld-35B-A3B-NVFP4`, **ctx 32k**,
  **Tool-Parser aktiv (verifiziert)** via `calculator {"expr":"12 * 7"}`.
- hermes `v0.17.0` in WSL vorhanden.

### Track-2-Pipeline end-to-end bewiesen
5 echte Terminal-Triples (Ground truth real in WSL ausgeführt) → beide Modelle sagen
next-state voraus → deterministisches Scoring. Läuft sauber gegen beide Endpoints.

### Zwei echte Bugs gefunden & behoben
1. **Leerer content durch Reasoning-Truncation.** Erster Lauf: A lieferte auf *alle*
   Triples `finish=length`, 1024 Tokens komplett im `<think>`-Block verbraucht, 0
   content. B teils auch (698–940 Tokens für ein Wort). → Fix: `enable_thinking=false`
   (chat_template_kwargs) für Track 2. Beide liefern jetzt direkte Observations in
   ~2 Tokens. Verifiziert auf A und B.
2. **Stateless-Shell-Ground-truth.** `gen_triples.py` führte jeden Befehl in einer
   frischen Shell aus → `cd` persistierte nicht → Aufgabe für die Modelle mehrdeutig
   (echte Terminals sind zustandsbehaftet). Ursache: stdout-Capture via `$(...)` =
   Subshell. → Fix: Brace-Group + Datei-Redirect im aktuellen Shell-Kontext, eine
   durchgehende Session. cwd/env persistieren jetzt korrekt.

### Offene Punkte (bevor Zahlen aussagekräftig sind)
- [ ] **Diskriminierende Triple-Suite.** Trivial-Sequenzen (echo/wc) → A und B scoren
      identisch. Brauchen härtere, diverse Fälle: Fehler/Tracebacks, mehrzeilige
      Ausgaben, git/pip/pytest, stateful Ketten, SWE-Repo-Zustände. Ziel 30–50 Triples.
- [ ] **Grader v2.** Aktuell zu grob: exit-code-Behandlung naiv, leere-stdout-Fälle
      nicht sinnvoll bewertbar, kein Teil-Credit für "fast richtig". Semantischeres
      Matching + die LLM-Judge-Dimensionen aktivieren (Cross-Judging A↔B, optional
      Claude als neutrale Gegenprobe).
- [ ] **Track 1 (Policy/hermes).** hermes-CLI-Flags gegen `hermes --help` verifizieren
      (`run_hermes_task()` ist markierter Adapter-Punkt), pytest in WSL installieren,
      SWE-Oracle end-to-end fahren.
- [ ] **Card-Regime.** Bisher nur `greedy`. `card`-Regime (temp 0.6/0.95/20) gegenlaufen.

### Hinweis zur Interpretation
Latenz/Speed wird **nicht** verglichen (verschiedene GPUs/Netz). Stichproben sind
klein → Richtungs-Indikatoren, keine Signifikanz. Siehe THREATS.md.
