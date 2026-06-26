# Scope & Limitations — bitte in jeden öffentlichen Beitrag übernehmen

Dieser Abschnitt ist absichtlich defensiv. Er grenzt ein, was die Zahlen sagen —
und was **nicht**.

## Was gemessen wurde
- **Modelle:** Qwen-AgentWorld-35B-A3B (NVFP4, 1× RTX PRO 5000 @ vast.ai) vs.
  Qwen3.6-27B (int4-AutoRound, 2× RTX 3090 lokal). „As deployed", nicht unquantisiert.
- **Aufgabe:** Next-State-Vorhersage in **2 von 7** Domänen — **Terminal** und ein
  bisschen **SWE**. Pro Triple: Verlauf + nächster Befehl → das Modell sagt die
  Terminal-Ausgabe voraus. **Ground Truth real ausgeführt** (kein Raten).
- **Setup:** offizielles AgentWorld-Setup (Thinking an, Domänen-System-Prompt,
  card-Sampling temp 0.6). **N = 2 Replikate**, 81 Triples je Lauf.
- **Judge:** ein **neutraler dritter** (mistral-small-24b @ OpenRouter), vor Einsatz
  validiert (wendet die „pre-existing = Plausibilität"-Regel an, wo gpt-4o-mini scheiterte).
- **Track 1 (Agent/hermes):** 3 SWE-Tasks, beide Modelle.

## Was die Zahlen sagen (robust über beide Replikate)
- **Genauigkeit gleichauf** (neutraler Judge ~83 vs ~84; Bereiche überlappen).
- **AgentWorld ~9× token-teurer** je Vorhersage (Median 510 vs ~4.700).
- **AgentWorld zuverlässiger** (fast nie leere Ausgabe: ~0,5 vs ~3,5 von 81).
- Beide lösen die getesteten Agent-Tasks (3/3).

## Was die Zahlen NICHT sagen
- **Keine Aussage über 5 der 7 Domänen** (Search, Android, Web, OS, MCP) — inkl. der
  GUI-Domänen, wo ein World Model anders abschneiden könnte.
- **Keine statistische Signifikanz.** N=2, eine Domäne, ein Sampling-Regime. Die
  Zahlen sind Spannweite, nicht Standardabweichung. Richtungs-Indikator.
- **Quant-Confound:** int4 vs NVFP4 — Unterschiede könnten teils Quantisierung sein.
- **Latenz/Speed NICHT verglichen** (verschiedene GPUs/Netz) — nur Token (faire
  Modell-Metrik).
- **Judge ist imperfekt** (schwankt bei manchen pre-existing-Fällen). Subjektive
  Dimensionen (Realism/Quality) mit Vorbehalt; Factuality/Recall sind robuster.
- Einzelne Vorhersagen mit Thinking können sehr lang/teuer werden; A produziert
  gelegentlich leere Ausgabe (im Empty-Rate erfasst).

## Ein-Satz-Fazit (zitierfähig)
> Auf reproduzierbaren Terminal-Next-State-Aufgaben ist AgentWorld-35B-A3B **nicht
> messbar genauer** als das generische Qwen3.6-27B — es ist **zuverlässiger**, aber
> **~9× token-teurer**. Die „3× besser / alle Agenten besser"-Behauptung ist auf
> dieser Basis **nicht gedeckt**.
