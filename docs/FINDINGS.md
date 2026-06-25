# FINDINGS

> Status: **Erstes belastbares Trennsignal da (Track 2, 26 harte Triples).**
> Vor dem Zitieren **[THREATS.md](THREATS.md) lesen** (int4 vs NVFP4, kleine N,
> nur Terminal-Domäne). Tabellen regenerierbar: `python scripts/make_report.py results/raw`.

## Headline

**Auf einer fairen, real-ausgeführten World-Model-Evaluation schlägt
AgentWorld-35B-A3B das generische Qwen3.6-27b NICHT — auch nicht auf seiner
eigenen Kern-Aufgabe (Next-State-Vorhersage).** Sie sind gleichauf. Der Hype
„3× besser / alle Agenten laufen besser" ist durch diese Messungen **nicht gedeckt**.

## Track 2 — World-Model-Fidelity (26 harte Terminal-Triples, greedy)

Aufgabe: gegeben Session-Verlauf + nächster Befehl → die reale Terminal-Ausgabe
vorhersagen. Ground truth echt in WSL ausgeführt (Tracebacks, Exit-Codes, git-Status,
mehrzeilige Outputs, stateful cd-Ketten).

| Metrik | A (Qwen3.6-27b) | B (AgentWorld-35B-A3B) |
|--------|----------------|------------------------|
| **Factuality (deterministisch, 0–100)** | **82.5** | **81.6** |
| Format (nicht-leer/valide) | 100 | 100 |
| Head-to-head (>3 Pkt. Diff.) | **2 Siege** | **1 Sieg** | 23× Gleichstand |

→ **Statistischer Gleichstand.** Beide verstehen Terminal-Semantik gut. Die zwei
echten Unterschiede heben sich nahezu auf:
- `git diff --numstat`: **A korrekt** (`1\t0\tr.txt`), **B falsch** (`0\t0\tr.txt`).
- `sort|uniq -c|sort -rn`: **B** trifft die Spalten-Formatierung besser als A.

### LLM-Judge: hier NICHT vertrauenswürdig (dokumentiert)
Cross-Judging (A↔B) ergab für **gleiche** Factuality stark divergierende Realism-Werte
(A bewertet durch B: 33.8; B bewertet durch A: 75.8). Das ist Judge-Identität, kein
Modell-Unterschied. Zwei Ursachen: (1) truth wurde dem Judge als JSON gezeigt → er
bestrafte Roh-Text-Vorhersagen fälschlich (Task verlangt aber Roh-Text); (2) A und B
als Judges sind unkalibriert. **Nur Consistency ist brauchbar** (beide ~90). Judge-Prompt
ist gefixt (`graders.py`); für belastbare Realism/Quality braucht es einen **neutralen,
kalibrierten** Judge (z. B. Claude) — offen.

## Track 1 — Hype-Test (Policy/Agent), Stand
Beide lösen den SWE-Bugfix (pytest grün). Trivial-Task → diskriminiert nicht; härtere
Agent-Suite steht noch aus. Operative Notiz: B's 32k war Serving-Default (Template),
inzwischen auf 256k korrigiert → kein Modell-Befund (s. THREATS §5c).

## Was damit gezeigt ist — und was nicht
**Gezeigt:** Auf 26 fairen, reproduzierbaren Terminal-Next-State-Aufgaben kein Vorteil
für AgentWorld. Das ist genau die Domäne, in der es laut Card glänzen soll.
**Nicht gezeigt:** Verhalten in den anderen 6 Domänen (Search/SWE/Android/Web/OS/MCP),
bei sehr langen/komplexen Szenarien, oder mit unquantisierten Gewichten. N=26, eine
Domäne, ein Sampling-Regime → **Richtungs-Indikator, kein Endurteil.**

## Nächste Schritte für mehr Konfidenz
1. `card`-Sampling-Regime gegenlaufen (temp 0.6/0.95/20) — Varianz prüfen.
2. Neutraler Judge (Claude) statt Cross-Judging → Realism/Quality belastbar.
3. SWE-Domänen-Triples (pytest-Output vorhersagen) + härtere Agent-Tasks (Track 1).
4. Triple-Zahl hoch (≥100) für tragfähigere Mittelwerte.
