# Track 3 — Closed-Loop: Ein Agent läuft gegen AgentWorld als Umgebung

## ☀️ Morgens-Statusbericht

> **TL;DR — die Antwort ist „es kommt drauf an", und zwar scharf.** Lässt man einen echten
> Agenten (Policy = Qwen3.6-27B) gegen AgentWorld (B) **als Umgebung** laufen, hängt alles
> daran, ob die Aufgabe den **simulierten Inhalt erzwingt**:
>
> | | **kurz** (agnostisch lösbar) | **lang/brutal** (Inhalt erzwungen) |
> |---|---|---|
> | Erfolg A@real (Baseline) | 100 % | 100 % |
> | **Erfolg A@sim** (Real-Replay) | **100 %** | **25 % (16.7–33.3)** |
> | **Getäuscht-Rate** | **0 %** | **25 % (16.7–33.3)** |
> | Divergenz / Schritt | 30 % | **87 %** |
>
> Bei **kurzen** Tasks rettet sich der Agent mit umgebungs-agnostischen Befehlen (`awk`,
> `sort -u`) — Per-Step-Fehler schaukeln sich NICHT auf. Sobald die Aufgabe ihn **zwingt**,
> halluzinierten Inhalt zu **lesen und literal darauf zu entscheiden**, kollabiert die
> Closed-Loop-Nutzung: nur noch 1 von 4 Aufgaben real gelöst, und in **1 von 4** glaubt der
> Agent fälschlich, fertig zu sein. Beides repliziert (2 Reps), oracle-basiert, 0 € extern.
> **Die ehrliche, vollständige Antwort auf „reicht ~84 % Per-Step-Fidelity für einen
> Live-Agenten?": Nein — sobald es auf den simulierten Inhalt ankommt.**

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

  Die **Langhorizont/Brutal-Zahlen** (N=6 × 2) stehen in §Track 3b — die Kurzfassung
  (25 % / 25 % / 87 %) ist oben im TL;DR und in `docs/charts/track3_compare.png`.
- **Was robust ist:** Beide Baselines 100 % über beide Reps. Der **Kontrast** kurz↔lang ist
  groß und in beiden Reps gleichgerichtet (Spannweiten überlappen nicht: sim-Erfolg 100 %
  vs 16.7–33.3 %). Das ist der belastbare Kern.
- **Was unsicher / zu beachten ist:** kleine N, **eine** Domäne (Terminal). Quant-Confound
  (A int4-autoround, B nvfp4). **B-Truncation** (32k-Deployment) in 3 langen Trajektorien →
  der Langhorizont-Einbruch ist teils Deployment-Limit, teils inhärent (s. §Track 3b, Pkt 4);
  mit ≥128k Kontext evtl. milder, aber Richtung bliebe.
- **Gefangene Bugs:** 1 (Divergenz-Artefakt bei Null-Output-Befehlen, im Smoke-Test vor dem
  Volllauf gefangen — siehe §Bugs).
- **Publikationsreif?** **Ja.** Sauberer identischer Baseline-Vergleich, oracle-basiert,
  repliziert, mit rückverfolgbaren Trajektorien-Belegen. Die Geschichte ist jetzt vollständig:
  **Per-Step-Fidelity ≠ Closed-Loop-Tauglichkeit**, und es hängt scharf am Aufgaben-Typ.

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

# Track 3b — Langhorizont-Brutal-Test

**Ziel:** Den Aufschaukel-/Täuschungs-Effekt **erzwingen**. 6 Aufgaben (`tasks/longhorizon/`),
bei denen der Agent halluzinierbaren Inhalt **lesen und darauf eine literale, schwer-skriptbare
Entscheidung treffen muss**: semantisches Verdikt (`interpret_verdict`), Transkription eines
entdeckten Werts (`copy_secret`), Verifikations-Schleife mit Erfolgssignal (`fix_until_check`),
7-Hop-Kette (`multi_hop_chain`), Max über 5 Reads (`inventory_audit`), bedingte Datei-Wahl
(`conditional_dispatch`). 2 Replikate, identisches Setup, nur die Umgebung unterscheidet sich.

## Ergebnisse (Langhorizont, N=6 Tasks × 2 Reps)

| Metrik | Wert (Mittel, Spannweite über Reps) |
|---|---|
| **Erfolg A@real** (Baseline, Oracle) | **100 % (100–100)** |
| **Erfolg A@sim** (Real-Replay, Oracle) | **25 % (16.7–33.3)** |
| **Getäuscht-Rate** (DONE, aber real gescheitert) | **25 % (16.7–33.3)** |
| **Divergenz / Schritt** (sim-Obs ≠ real-Obs) | **87.3 % (86.4–88.2)** — gepoolt 87.4 %, n=95 |
| Token/Schritt Median — A (Policy) / B (Sim) | 70 / 7686 |

| Task | real | sim-replay | getäuscht | Divergenz/Schritt |
|---|---|---|---|---|
| interpret_verdict | 2/2 | **2/2** | 0 | 50.0 % |
| inventory_audit | 2/2 | 1/2 | 0 | 90.9 % |
| conditional_dispatch | 2/2 | **0/2** | **2** | 50.0 % |
| copy_secret | 2/2 | **0/2** | 0 | 100.0 % |
| fix_until_check | 2/2 | **0/2** | **1** | 86.7 % |
| multi_hop_chain | 2/2 | **0/2** | 0 | 96.4 % |

Charts: `docs/charts/track3_compare.png` (Headline: kurz vs lang), `docs/charts/track3_lh_success.png`,
`docs/charts/track3_lh_divergence.png`.

## Zwei Belege aus den Trajektorien (rückverfolgbar in `results/raw/`)

**1) Täuschung — `conditional_dispatch` (B erfindet sogar einen Hostnamen):**
```
[0] cat health.txt   SIM: 'health check: ok'     REAL: 'status: degraded'
[1] cat hostname.txt  SIM: 'agentworld-12'        REAL: 'primary-db-01'
[2] echo "agentworld-12" > ok_hosts.txt   (Agent glaubt "healthy" -> falsche Datei, falscher Host)
-> Agent sagt DONE. Real-Replay: ok_hosts statt alert_hosts, 'agentworld-12' statt 'primary-db-01' -> FAIL.
```
B halluziniert den Status (`ok` statt `degraded`) → der Agent wählt den falschen Zweig **und**
schreibt einen von B frei erfundenen Hostnamen (ironischerweise „agentworld-12"). Real-Replay
scheitert, der Agent merkt es nicht → **Täuschung**.

**2) Aufschaukeln — `multi_hop_chain` (B hält die Kette, verliert aber die Nutzlast):**
```
[0..5] cat start/blue/.../frost   SIM: 'start -> blue' ... 'frost -> grove'   (Kette konsistent!)
[6]    cat grove.txt              SIM: 'grove -> the final step'   REAL: 'The password is: vortex'
[7..13] grep/cat/ls (Agent sucht verzweifelt das Passwort)  SIM liefert leer/falsch -> nie 'vortex'
-> max_steps, password.txt nie geschrieben -> FAIL.
```
B bleibt über 6 Hops **selbst-konsistent** (formuliert „Open blue.txt" zu „start -> blue" um),
**fabriziert aber die eigentliche Nutzlast** am Endknoten. Der Agent probiert danach 7 weitere
Befehle — B kann die Wahrheit (`vortex`) nicht mehr hervorbringen, weil sie nie in seinem
halluzinierten Zustand war. Genau das ist der Aufschaukel-Effekt, sichtbar gemacht.

## Interpretation (ehrlich)

1. **Die Kurzhorizont-„Robustheit" war ein Artefakt der Aufgaben, nicht des Simulators.**
   Sobald die Aufgabe den Agenten zwingt, B's Ausgabe **inhaltlich** zu nutzen, bricht der
   Erfolg von 100 % auf **25 %** ein und die Divergenz steigt von 30 % auf **87 %/Schritt**.
2. **Täuschung ist real und häufig:** 25 % — jede vierte Episode endet damit, dass der Agent
   `DONE` sagt, obwohl real nichts gelöst ist. Für einen Live-Agenten ist das das gefährlichste
   Versagen (still, unbemerkt). `fix_until_check` zeigt den klassischen Fall: B liefert ein
   halluziniertes Erfolgssignal, der Agent hört auf.
3. **B ist überraschend gut in struktureller Konsistenz, schlecht in faktischem Inhalt.** Die
   Kette blieb über 6 Hops formal stimmig; was es nicht kann, ist **konkrete, nie gesehene
   Inhalte** (Passwörter, Tokens, exakte Datei-Inhalte) treu halten — genau die, von denen der
   Task-Erfolg abhängt. Der einzige sim-Erfolg (`interpret_verdict`) überlebt nur, weil dort
   die **semantische Essenz** („Build fehlgeschlagen") zählt, nicht ein exakter Wert.
4. **Confound dokumentiert:** B (32k-Kontext-Deployment) lief in den langen Trajektorien
   **3× in Truncation** (`finish_reason=length`) → teils leere Vorhersagen. Das ist teils
   Deployment-Limit (Card empfiehlt ≥128k), teils inhärent: lange Closed-Loop-Rollouts sprengen
   ein 32k-Fenster. Der Harness behandelt leere B-Ausgaben sauber (gezählt, kein Crash). Mit
   größerem Kontext könnte der Effekt **milder** sein — die Richtung (Inhalts-Treue bricht)
   bliebe.

## Gesamt-Fazit Track 3 (für den Artikel)

„AgentWorld als Live-Umgebung für einen Agenten" funktioniert in unserem Test **nur für
Aufgaben, die der Agent ohnehin umgebungs-agnostisch löst** — dort trägt es nichts bei außer
~9× Token-Kosten (Track 2) und 30 % Rausch-Divergenz, die folgenlos bleibt. **Sobald die
Aufgabe den simulierten Inhalt erzwingt, kollabiert die Closed-Loop-Nutzung** (Erfolg 25 %,
Täuschung 25 %, Divergenz 87 %). Per-Step-Fidelity (~84–98 % in Track 2) ist also **kein
Prädiktor** für Closed-Loop-Tauglichkeit. Das ist weder ein Verriss noch ein Lob — es ist die
saubere Abgrenzung, **wofür ein Terminal-World-Model heute taugt (Plausibilität/Struktur) und
wofür nicht (treuer Live-Ersatz für echte Tools)**.

## Reproduktion (Langhorizont)

```bash
python scripts/make_longhorizon_tasks.py
python harness/run_track3_closedloop.py --env real --suite longhorizon --reps 2
python harness/run_track3_closedloop.py --env sim  --suite longhorizon --reps 2
python scripts/report_track3.py results/raw docs/data/track3_longhorizon_summary.json longhorizon
python scripts/make_charts_track3.py
```
