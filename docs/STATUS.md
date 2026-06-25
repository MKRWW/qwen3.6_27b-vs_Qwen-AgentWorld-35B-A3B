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

## 2026-06-25 (Forts.) — Track 1 (hermes/Policy) end-to-end

### hermes-Integration geknackt (beide Modelle)
hermes hat **kein** `run`-Subcommand → One-Shot via `-z`. Nicht-invasiv über
isoliertes `HERMES_HOME`. Volle Recipe + 4 Stolpersteine in
[HERMES_SETUP.md](HERMES_SETUP.md).

- **A (Qwen3.6)** lief ohne Workaround.
- **B (AgentWorld)** brauchte: api_key in Config (401), context_length=64000 an zwei
  Stellen (32k < hermes-Floor 64k), max_tokens=2048 (sonst `'final_response'`-Crash,
  weil hermes 65k Output anforderte > B's 32k-Fenster).

### Erster echter SWE-Task end-to-end (reproduzierbar via Code)
`run_track1_policy.py` neu: isolierte Bench-Homes, WSL-Sandbox, pytest-Oracle in
dedizierter venv (`~/.cache/awbench-venv`), base64-robustes Result-Parsing.
- Buggy → pytest FAIL; **A** fixt korrekt → PASS; **B** fixt korrekt → PASS.
- Beide bestehen den Trivial-Task → diskriminiert (noch) nicht.

### Befund
Qualitativ robust: **B's 32k-Kontext liegt unter hermes' 64k-Floor** → vier
Eingriffe nötig, damit B als Agent überhaupt startet. A „lief einfach". Das ist
reale Friktion gegen „alle Agenten laufen besser". Siehe [FINDINGS.md](FINDINGS.md).

### Noch offen (für belastbare Zahlen)
- [ ] Diskriminierende Task-/Triple-Suite (beide Tracks).
- [ ] Grader v2 + LLM-Judge aktivieren.
- [ ] `card`-Regime gegenlaufen.

### Hinweis zur Interpretation
Latenz/Speed wird **nicht** verglichen (verschiedene GPUs/Netz). Stichproben sind
klein → Richtungs-Indikatoren, keine Signifikanz. Siehe THREATS.md.

## 2026-06-25 (Forts. 2) — B auf 256k, erster harter Track-2-Lauf

- vast-Claude bestätigt: 32k war nur **Template-Default** (VLLM_ARGS), nicht VRAM.
  Hybrid-Arch (30 Linear- + 10 Full-Attn-Layer) → KV-Cache winzig; max-model-len
  höher kostet 0 VRAM. **Auf 262144 (256k) gesetzt.** Asymmetrie weg.
- Grader v2 (difflib-Ähnlichkeit, stderr, gewichtet), gen_triples `--prefix`,
  5 harte Sequenzen → **26 Triples** (Fehler/Traceback/Python/Textproc/git/stateful).
- **Track-2-Lauf (greedy, Judge an):** Factuality **A=82.5 vs B=81.6 → Gleichstand**.
  Head-to-head 2:1:23. AgentWorld auf seiner Kern-Aufgabe **nicht** besser.
- Judge unbrauchbar hier (JSON-Artefakt + unkalibrierte Cross-Judges) → Prompt
  gefixt, Realism/Quality bis neutraler Judge ausgesetzt. Details: FINDINGS.md.

### Noch offen
- [ ] card-Regime; neutraler Judge (Claude); SWE-Triples; N≥100; härtere Track-1-Tasks.

## 2026-06-25 (Forts. 3) — Track-2-Testfehler gefunden & behoben (Skepsis-getrieben)

Nutzer-Frage „haben wir keinen Testfehler? sind die Aufgaben zu leicht?" → Card neu
gelesen. **Wir hatten Thinking abgeschaltet** (`enable_thinking=false`) — genau B's
State-Mechanismus. Dazu generischer statt offizieller Prompt, falsches Input-Format,
greedy statt card. Korrigiert: offizielle Domänen-Prompts aus dem Repo, multi-turn
`Action/Command`-Format, Thinking AN, Grader v3 (Recall über sichtbaren Screen).

Iteration (Test-Validität):
- Lauf 8192: B 7× leer (`finish=length`) — **mein Limit**, nicht B. Card nennt 32768.
- Lauf 32768: **A=98.3, B=98.3 (Genauigkeit identisch)**, aber B median **4348 vs 454
  completion_tokens → ~9× teurer** für dasselbe Ergebnis.

**Fazit Track 2:** AgentWorld auf Terminal-Next-State nicht genauer, nur ~9× token-
hungriger. ABER beide bei 98.3 = **Ceiling** → Aufgaben evtl. zu leicht; echter
World-Model-Vorteil bräuchte pre-existing-State/lange Trajektorien/GUI-Domänen.
