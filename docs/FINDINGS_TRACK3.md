# Track 3 — Closed-Loop: Ein Agent läuft gegen AgentWorld als Umgebung

## ☀️ Morgens-Statusbericht

> **TL;DR:** Im Closed-Loop löst ein echter Agent (Policy = Qwen3.6-27B) **alle** Tasks
> sowohl gegen die echte Umgebung als auch gegen AgentWorld als Simulator — **trotz ~30 %
> Per-Step-Divergenz** und **ohne eine einzige Täuschung**. Die „Per-Step-Fehler schaukeln
> sich zu Task-Versagen auf"-Hypothese ist für **kurze, robuste-Befehl-Tasks widerlegt**.
> Der Grund ist aber nuanciert (und nicht unbedingt ein Lob für B) — siehe Interpretation.
> Ein **Langhorizont-Brutal-Test** (erzwingt Konsum halluzinierter Inhalte) läuft separat
> und wird unten angehängt.

- **Was gemessen:** ReAct-Agent A löst 8 shell-lösbare Multi-Step-Tasks, einmal gegen die
  **echte** WSL-Sandbox (`real`, Baseline), einmal gegen **AgentWorld-35B-A3B („B")** als
  simulierte Umgebung (`sim`, Closed-Loop auf B's eigenen Vorhersagen). 2 Replikate je
  Bedingung (temp 0.6). Bewertung **oracle-basiert** (deterministisch) → 0 € externe Kosten.
- **Kernzahlen (kurze Horizonte, N=8 Tasks × 2 Reps):**

  | Metrik | Wert (Mittel, Spannweite über Reps) |
  |---|---|
  | **Erfolg A@real** (Baseline, Oracle) | **100 % (100–100)** |
  | **Erfolg A@sim** (Real-Replay, Oracle) | **100 % (100–100)** |
  | **Getäuscht-Rate** (DONE, aber real gescheitert) | **0 % (0–0)** |
  | **Divergenz / Schritt** (sim-Obs ≠ real-Obs) | **29.7 % (28.6–30.8)** — gepoolt 29.6 %, n=27 |
  | Token/Schritt Median — A (Policy) / B (Sim) | 70 / 5348 |

- **Was robust ist:** Baseline-Erfolg (100 %) und Real-Replay-Erfolg (100 %) sind über
  beide Reps identisch. Die Divergenz-Spannweite ist eng (28.6–30.8 %).
- **Was unsicher / zu beachten ist:** kleine N, eine Domäne (Terminal), **kurze Horizonte**
  (Tasks in 1–3 Schritten lösbar → der Aufschaukel-Effekt wird konservativ getestet).
  Quant-Confound (A int4-autoround, B nvfp4). Deshalb der Langhorizont-Test (unten).
- **Gefangene Bugs:** 1 (Divergenz-Artefakt, im Smoke-Test gefangen — siehe §Bugs).
- **Publikationsreif?** **Ja** für die kurze-Horizont-Aussage (sauberer Baseline-Vergleich,
  Oracle-basiert, repliziert). Die *vollständige* Geschichte braucht den Langhorizont-Teil.

---

## Die Frage (warum dieser Track existiert)

Track 2 zeigte ~84–98 % **Per-Step**-Fidelity. Der eigentliche Verwendungszweck eines World
Models ist aber nicht Single-Step-Vorhersage, sondern: **ein Agent läuft live gegen das
Modell als Umgebung** (Mock-API). Offene Frage: **Reicht Per-Step-Fidelity, damit ein echter
Agent eine GANZE Aufgabe gegen die simulierte Umgebung löst** — oder schaukeln sich Fehler
über den Rollout auf (84 %^N)? Und: wie oft wird der Agent **getäuscht** (glaubt Erfolg, real
gescheitert)?

## Design (fair, identisch, nur die Umgebung unterscheidet sich)

- **Policy = Modell A** (Qwen3.6-27B): entscheidet je Schritt **einen** Shell-Befehl
  (`CMD: …`) oder `DONE`. Identischer Prompt/Settings in beiden Bedingungen.
- **Umgebung austauschbar:**
  - `real`: echte persistente WSL-Sandbox. Oracle = Wahrheit.
  - `sim`: **AgentWorld (B)** sagt die nächste Terminal-Observation voraus — **offizielles
    Setup laut Model-Card** (verifiziert, s. u.). **Closed-Loop:** B konditioniert auf seine
    **eigenen** früheren vorhergesagten Screens → Fehler können sich aufschaukeln.
- **Bootstrap (Fairness):** Beide Bedingungen starten mit demselben realen `ls -la` als
  „initialisiertem" Umgebungs-Zustand (so wird AgentWorld real benutzt — der Simulator kennt
  die Anfangs-Datei-Liste). B muss dann **Inhalte & Effekte** vorhersagen.
- **Bewertung — 3 Sichten:** (1) **Erfolg A@real** (Oracle, Baseline); (2) **Erfolg A@sim
  Real-Replay** (in der Sim erzeugte Befehlssequenz in **frischer echter Sandbox**
  nachgespielt + Oracle); (3) **Getäuscht-Rate** (Agent sagt `DONE`, aber Real-Replay
  scheitert). Plus **Divergenz/Schritt** (jeder sim-Befehl parallel real ausgeführt).

### Offizielles B-Setup — verifiziert gegen die Model-Card

[huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B)
bestätigt exakt unser Setup: domänenspezifischer Terminal-System-Prompt aus dem Repo
(`config/prompts/terminal/system_prompt.txt`), **Thinking-Mode AN** (default, `<think>…</think>`,
`--reasoning-parser qwen3`), **Sampling temp 0.6 / top_p 0.95 / top_k 20** (= unser `card`-
Regime, identisch), Aktions-Format `Action: execute_bash` / `Command: …`. **Einzige Abweichung:**
empfohlenes Output-Budget bis 32 768 bei ≥128k Kontext — diese vast-Deployment serviert nur
**32k Kontext**, daher Output-Cap 16 384 (dokumentierter Confound, unverändert aus Track 2).

## Ausführungs-Modell (robust & reproduzierbar)

Jede reale Auswertung ist eine **reine Funktion** `run_sequence(task, commands)`: frische
WSL-Sandbox → `setup.sh` seedet (relative Pfade, deterministisch) → die **ganze**
Befehlssequenz läuft in **einem** persistenten bash-Driver (cd/export persistieren via
Brace-Group statt Subshell) → pro Schritt base64-Marker (stdout/stderr/exit/cwd/fs_delta) →
`oracle.sh`. Idempotent, weil jede Invocation frisch seedet und voll nachspielt — kein
fragiler interaktiver Pipe-State auf Windows.

## Tasks (8, `tasks/closedloop/`)

`create_file`, `count_lines`, `rename_file`, `append_line`, `mkdir_move`, `grep_filter`,
`sum_numbers`, `sort_unique`. Alle: relative Pfade, deterministischer Inhalt, Oracle
**diskriminiert** (verifiziert: Start-Zustand ⇒ Oracle FAIL).

## Ergebnisse (Pro Task, über Reps)

| Task | real | sim-replay | getäuscht | Divergenz/Schritt |
|---|---|---|---|---|
| append_line | 2/2 | 2/2 | 0 | 33.3 % |
| count_lines | 2/2 | 2/2 | 0 | 25.0 % |
| create_file | 2/2 | 2/2 | 0 | 0.0 % |
| grep_filter | 2/2 | 2/2 | 0 | 50.0 % |
| mkdir_move | 2/2 | 2/2 | 0 | 50.0 % |
| rename_file | 2/2 | 2/2 | 0 | 0.0 % |
| sum_numbers | 2/2 | 2/2 | 0 | 50.0 % |
| sort_unique | 2/2 | 2/2 | 0 | 0.0 % |

Charts: `docs/charts/track3_success.png`, `docs/charts/track3_divergence.png`.

## Interpretation (ehrlich, ohne Schönfärben in beide Richtungen)

1. **Per-Step-Fehler ≠ Task-Versagen.** B sagt ~30 % der Schritte falsch voraus, doch der
   Agent löst 100 %. Die naive „84 %^N → Kollaps"-Rechnung **stimmt so nicht**, weil die
   Schritte nicht unabhängig kausal sind: eine kompetente Policy schreibt **umgebungs-
   agnostische** Befehle (`awk 'END{print NR}'`, `sort -u`, `grep apple … > out`), deren
   *realer* Effekt unabhängig davon ist, was B als Zwischen-Observation halluziniert.
2. **Das ist nicht automatisch ein Lob für B.** Der Erfolg kommt **trotz** schlechter
   Simulation zustande, nicht **wegen** guter — er ist ein Verdienst der **Policy** (A), die
   robuste Befehle wählt, nicht des **Simulators** (B). Die Divergenz von 30 % zeigt: als
   *treuer* Umgebungs-Spiegel ist B hier eher mittelmäßig; es rettet nur, dass die Aufgaben
   keine Abhängigkeit vom halluzinierten Inhalt erzwingen.
3. **Die Täuschungsgefahr ist real, materialisiert sich hier aber nicht.** Getäuscht-Rate
   0 %. Genau deshalb der Langhorizont-Test: Aufgaben, die den Agenten **zwingen**,
   halluzinierte Inhalte zu lesen und darauf eine literale Entscheidung zu treffen — dort
   sollte (falls die Hypothese stimmt) die Divergenz in **Real-Replay-Versagen + Täuschung**
   umschlagen.

## Bugs gefangen & gefixt (Lab-Notebook)

1. **Divergenz-Artefakt bei Null-Output-Befehlen.** Der Per-Step-Divergenz-Vergleich stellte
   den policy-seitigen Platzhalter `(no output; exit code 0)` (real) gegen die leere
   Sim-Ausgabe `''` → 100 % „Divergenz" für jeden Redirect/`mkdir`/`mv`-Schritt, obwohl beide
   semantisch identisch „kein Output" sind. **Fix:** Divergenz vergleicht jetzt den **reinen**
   Befehls-Output (`raw_output()`), nicht den Anzeige-Platzhalter. Im Smoke-Test gefangen
   (`create_file` zeigte div=1.0), **bevor** der Volllauf startete.

## Scope & Limitations (explizit)

- **N klein:** 8 Tasks, 2 Replikate, **eine** Domäne (Terminal). Richtungs-Indikator.
- **Kurze Horizonte:** Eine starke Policy löst die meisten Tasks mit umgebungs-agnostischen
  One-Linern in 1–3 Schritten → der Aufschaukel-Effekt ist hier konservativ getestet. Der
  Langhorizont-Test (unten) adressiert genau das.
- **Quant-Confound:** A int4-autoround, B nvfp4 (unverändert aus Track 1/2).
- **Sim-Extraktion:** Reine Observation wird aus B's Screen geparst (Echo-Zeile → bis zum
  nächsten Prompt); Parser-Fehlschläge werden geloggt, Raw-Screen bleibt erhalten.

## Reproduktion

```bash
python harness/run_track3_closedloop.py --env real --suite closedloop --reps 2
python harness/run_track3_closedloop.py --env sim  --suite closedloop --reps 2
python scripts/report_track3.py results/raw docs/data/track3_summary.json closedloop
python scripts/make_charts_track3.py
```

---

# Track 3b — Langhorizont-Brutal-Test  _(läuft — wird angehängt)_

**Ziel:** Den Aufschaukel-/Täuschungs-Effekt **erzwingen**. Aufgaben, bei denen der Agent
halluzinierte Inhalte **lesen und darauf eine literale, nicht-skriptbare Entscheidung
treffen muss** (semantische Verdikte, Mehr-Hop-Ketten, Verifikations-Schleifen, Transkription
entdeckter Werte). Hypothese: Erfolg A@sim bricht ein und/oder Getäuscht-Rate steigt deutlich.
Setup, Zahlen und Interpretation werden hier nach dem Lauf ergänzt.
