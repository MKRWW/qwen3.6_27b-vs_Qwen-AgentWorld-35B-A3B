# FINDINGS

> Status: **Track 2 mit dem OFFIZIELLEN AgentWorld-Setup sauber gemessen.**
> Vor dem Zitieren **[THREATS.md](THREATS.md) lesen** (nur Terminal-Domäne, N=26,
> Ceiling-Effekt). Tabellen: `python scripts/make_report.py results/raw`.

## Headline

Auf **leichten, deterministischen** Terminal-Aufgaben sind AgentWorld-35B-A3B (B) und
das generische Qwen3.6-27b (A) **gleich genau** (98.3 / 98.3) — aber B braucht **~9×
mehr Tokens**. Erst auf **schwereren** Aufgaben (pre-existing-State-Plausibilität,
langes Multi-Turn-State-Tracking) zeigt B einen **echten, aber moderaten Vorteil** —
genau dort, wofür ein World Model gebaut ist. **Kein „3× besser", aber auch nicht
nichts:** ein realer Edge auf den richtigen Aufgaben, erkauft mit ~9× Token-Kosten.

## Anti-Ceiling-Lauf (18 Triples: 8 pre-existing + 10 long-chain), neutral gejudged

Auf den leichten Triples (98.3 = Ceiling) sah man nichts. Diese Suite testet, wo ein
World Model glänzen *müsste*. Bewertung durch **einen neutralen Judge (Claude, gleiche
offizielle Rubrik für beide)** — weil Cross-Judging A/B unterschiedlich streng wertet
und damit unvergleichbar ist (A-Judge wendet „Plausibilität" für Versionen korrekt an,
B-Judge nicht).

**Long-chain (State über 10 Turns):**
- `longchain_09` (`cd ../.. && basename $(pwd)`, Wahrheit `lab`): **A falsch** (`demo` —
  verwechselt `$PROJ`-Wert mit Verzeichnis), **B korrekt** (`lab`). B hält cwd sauber.
- B emittiert konsequent das offizielle Screen-Format (Prompt+Echo+Prompt); A gibt
  teils nur nackten Output → B „terminal-nativer".

**Pre-existing (Plausibilität, neutrale Brille):**

| Aufgabe | A | B | Sieger |
|---------|---|---|--------|
| `uname -s -m` | in Markdown-Fences ``` ``` (unrealistisch) | sauber `Linux x86_64` | **B** |
| `git --version` | 2.34.1 | 2.43.0 (= Wahrheit) | **B** |
| `ls /usr/lib/python3.12` | 0/5 echte Datei-Namen | 3/5 echte (`__future__.py` …) | **B** |
| `head -2 /etc/os-release` | PRETTY_NAME zuerst (korrekt) | NAME (falsche Zeile) | **A** |
| python-Version / whoami / nproc / hostname | identisch / beide plausibel | dito | Gleichstand |

**Neutrale Bilanz: B 3 : A 1 : 3 Gleichstand** bei pre-existing, **plus** B gewinnt den
tiefen Multi-Turn-Fall. → Erster belastbarer **Vorteil für AgentWorld** auf seiner
Kern-Kompetenz (plausible Umgebungs-Simulation, langes State-Tracking).

> Mess-Lehre: Cross-Judging ist für A-vs-B **ungeeignet** (unkalibrierte Judges).
> Fairer Vergleich braucht **einen** Judge für beide — hier Claude; reproduzierbar
> wäre ein fixer neutraler Judge-Endpoint.

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
**Gezeigt:** (1) Auf leichten, deterministischen Terminal-Aufgaben kein Genauigkeits-
Vorteil (98.3 = Ceiling), bei ~9× Token-Kosten für B. (2) Auf schwereren Aufgaben
(pre-existing-Plausibilität, langes State-Tracking) ein **moderater, realer Vorteil für
B** (neutral gejudged 3:1 + der tiefe Multi-Turn-Fall) — dort, wofür es gebaut ist.
**NICHT gezeigt:** Ausmaß über N=18 hinaus, andere Domänen (Web/Android/SWE/…), ob der
Edge „3× besser" je erreicht (klar nein bisher), unquantisiert. Eine Domäne, ein Regime,
kleine N → Richtungs-Indikator.

## Nächste Schritte für ein Endurteil
1. **Härtere Triples gegen den Ceiling:** pre-existing-State (cat unbekannter Files,
   `pip show`, `apt`-Listen), lange Multi-Turn-Ketten, interaktive Programme (vim/REPL).
2. Offizieller **judge_system_prompt** (unterscheidet deterministisch vs pre-existing)
   statt nur Recall — fairer für genau diese harten Fälle.
3. SWE-Domäne (pytest-Output vorhersagen) + andere Domänen.
4. Token-Effizienz als feste Metrik in den Report.
