# FINDINGS

> Status: **Track 2 mit dem OFFIZIELLEN AgentWorld-Setup sauber gemessen.**
> Vor dem Zitieren **[THREATS.md](THREATS.md) lesen** (nur Terminal-Domäne, N=26,
> Ceiling-Effekt). Tabellen: `python scripts/make_report.py results/raw`.

## Headline

Mit dem **offiziellen Setup** (Thinking an, AgentWorlds eigene Domänen-Prompts,
ausreichend Token-Budget) sagt AgentWorld-35B-A3B Terminal-Zustände **genauso genau**
vorher wie das generische Qwen3.6-27b — **aber mit ~9–10× so vielen Tokens**. Auf
seiner Kern-Aufgabe ist es also **nicht besser, nur teurer**. Der Hype „3× besser"
ist auf dieser Domäne nicht gedeckt.

## Track 2 — World-Model-Fidelity (26 harte Terminal-Triples, offizielles Setup)

| Metrik | A (Qwen3.6-27b) | B (AgentWorld-35B-A3B) |
|--------|----------------|------------------------|
| **Factuality (Recall sichtbarer stdout/stderr-Zeilen, 0–100)** | **98.3** | **98.3** |
| Triples mit 100 | 25/26 | 25/26 |
| **completion_tokens — Median** | **454** | **4 348** |
| completion_tokens — Mean / Max | 559 / 1 797 | 4 328 / 11 320 |

- **Genauigkeit gleichauf.** Beide treffen 25/26 exakt. Der einzige Nicht-Treffer
  (`errors_04`, `ls /root/private_xyz`) ist bei *beiden* identisch 57.1 — ein
  pre-existing-state-Fall (Permission denied vs No such file), den der deterministische
  Grader hart wertet; AgentWorlds eigener Judge würde hier „nur Plausibilität prüfen".
- **Effizienz: B braucht ~9.6× mehr Tokens** (Median 4 348 vs 454). B erzeugt ~4 000
  versteckte Denk-Tokens und dann eine kurze, korrekte Antwort; A kommt mit ~450 zum
  selben Ergebnis. Das ist faire Modell-Metrik (kein GPU/Netz).

### Warum das Ergebnis dreimal kippte (Test-Validität, transparent)
| Lauf | Setup | A / B | Lehre |
|------|-------|-------|-------|
| 1 | greedy, **Thinking AUS**, generischer Prompt, max 1024 | 82.5 / 81.6 | **Fehler:** wir hatten genau B's State-Mechanismus (Thinking) abgeschaltet |
| 2 | card, Thinking AN, **offizieller** Prompt, max 8192 | 98.4 / 7× leer | **Fehler:** Budget zu klein → B truncated (braucht real ~9–11k) |
| 3 | card, Thinking AN, offiziell, **max 32768** | **98.3 / 98.3** | sauber |

→ Die ersten beiden „Befunde" waren **Test-Artefakte**, kein Modellverhalten. Erst
Lauf 3 ist belastbar. (Dank an die Skepsis, die das aufgedeckt hat.)

## Track 1 — Hype-Test (Policy/Agent), Stand
Beide lösen den SWE-Bugfix (pytest grün). Trivial → diskriminiert nicht; härtere
Agent-Suite offen. B-Serving auf 256k korrigiert (32k war Template-Default).

## Was gezeigt ist — und was NICHT
**Gezeigt:** Auf 26 fairen Terminal-Next-State-Aufgaben kein Genauigkeits-Vorteil für
AgentWorld bei ~9× Token-Kosten.
**NICHT gezeigt / offene Schwäche des Tests:** Beide bei **98.3 → Ceiling-Effekt**. Die
Aufgaben sind „deterministisch" (Output folgt zwingend aus Befehl + Session) und damit
evtl. zu leicht, um einen echten World-Model-Vorteil sichtbar zu machen. Wo B *glänzen*
könnte: pre-existing-State-Inferenz (unbekannte Dateiinhalte/Paketversionen), sehr lange
Multi-Turn-Trajektorien, GUI-Domänen (Web/Android). N=26, eine Domäne, ein Regime.

## Nächste Schritte für ein Endurteil
1. **Härtere Triples gegen den Ceiling:** pre-existing-State (cat unbekannter Files,
   `pip show`, `apt`-Listen), lange Multi-Turn-Ketten, interaktive Programme (vim/REPL).
2. Offizieller **judge_system_prompt** (unterscheidet deterministisch vs pre-existing)
   statt nur Recall — fairer für genau diese harten Fälle.
3. SWE-Domäne (pytest-Output vorhersagen) + andere Domänen.
4. Token-Effizienz als feste Metrik in den Report.
