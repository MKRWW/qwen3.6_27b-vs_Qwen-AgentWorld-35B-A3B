# Threats to Validity — bitte vor dem Zitieren von Zahlen lesen

Dieser Benchmark vergleicht **zwei Deployments wie sie beim Nutzer real laufen**.
Das ist absichtlich, aber es ist **kein** sauberer Modell-gegen-Modell-Vergleich.
Hier ist offen, was die Ergebnisse verzerrt.

## 1. Quantisierung (groß)
- **A (Qwen3.6-27b) läuft int4 (AutoRound), B (AgentWorld) läuft NVFP4.**
- Beide sind 4-bit-quantisiert, aber unterschiedliche Schemata (AutoRound-int4 vs
  NVFP4). Qualitätsverlust ist bei beiden möglich und nicht symmetrisch.
- *Minderung:* als Vorbehalt benennen; keine Aussage über die unquantisierten Modelle.

## 2. Unterschiedlicher Modell-Zweck (der Kernpunkt)
- B ist ein **World Model**, A ein **Policy-Modell**. Track 1 testet B außerhalb
  seines Designs, Track 2 testet A außerhalb seines Designs.
- Das ist gewollt (wir prüfen den Hype), aber Einzelzahlen aus dem "falschen" Track
  dürfen **nicht** als generelles "X ist schlechter" verkauft werden.

## 3. Parameter / Architektur
- 27B (A) vs 35B-A3B MoE mit 3B aktiv (B). Weder Gesamt- noch Aktiv-Parameter sind
  gleich. "Größer" ≠ "besser", aber es ist eine Variable, die wir nicht kontrollieren.

## 4. Latenz / Netzwerk / GPU (KEINE Vergleichsmetrik)
- A: LAN, 2× RTX 3090. B: Remote vast.ai, 1× RTX PRO 5000. Komplett verschiedene
  Hardware UND Netzwerkpfade.
- `wall_clock_s` und tok/s werden **nur informativ geloggt** und gehen **nicht** in
  die Bewertung ein. Speed-Aussagen wären Äpfel-mit-Birnen.

## 5. Tool-Parser  (RESOLVED)
- Beide Endpoints haben einen aktiven Tool-Call-Parser — für B per Probe verifiziert
  (`calculator {"expr":"12 * 7"}` korrekt zurückgegeben).
- Damit ist Track 1 fair: B "verliert" nicht aus reinem Serving-Grund. Falls trotzdem
  einzelne malformed Tool-Calls auftreten, zählen sie inhaltlich (in `tool_call_valid_rate`).

## 5b. Kontext-Cap (Fairness)
- B serviert nur 32k Kontext, A 262k. Beide Prompts werden auf **32k** begrenzt,
  damit kein Modell durch mehr/weniger Kontextfenster bevor-/benachteiligt wird.

## 6. Reasoning-Budget / leerer Content
- Beide sind Reasoning-Modelle. Zu kleines `max_tokens` → Budget im Denk-Teil
  aufgebraucht → leerer `content`. Wir setzen großzügige Limits und loggen
  `finish_reason`; abgeschnittene Antworten werden markiert, nicht als
  inhaltlicher Fehler gewertet.

## 7. LLM-Judge-Bias (Track 2)
- Subjektive Dimensionen (Realism/Quality/Consistency) per LLM-Judge → Judge-Bias.
- *Minderung:* fixer Judge-Prompt, temp=0, **kein Self-Judging**, Begründungen
  werden mitgeloggt und sind stichprobenartig manuell prüfbar. Optional Claude als
  zweiter Judge zur Korrelationsprüfung.

## 8. Stichprobengröße
- 8–12 Tasks / 30–50 Triples. **Keine statistische Signifikanz.** Befunde sind
  Richtungs-Indikatoren. Konfidenzintervalle wären bei dieser N irreführend.

## 9. Task-Auswahl-Bias
- Wir schreiben die Tasks selbst. Risiko, (unbewusst) Tasks zu wählen, die eine
  These bestätigen. *Minderung:* Tasks vor den Runs committen (Git-Historie als
  Zeitstempel), Auswahlkriterien dokumentieren, keine Tasks nach Sichtung der
  Ergebnisse nachträglich entfernen.

## 10. Determinismus
- vLLM temp=0 ist nicht bit-genau garantiert (Batching/Kernel). `greedy` ist
  Stabilitäts-Anker, keine Bit-Garantie.

## 11. Datenkontamination
- Unbekannt, ob AgentWorldBench-artige Triples in B's Training waren. Eigene,
  frisch generierte Triples mindern das, schließen es aber nicht aus.
