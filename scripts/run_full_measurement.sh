#!/usr/bin/env bash
# Komplette, reproduzierbare Messung (Track 1 + Track 2) -> results/raw/ + Report.
# Aufruf aus dem Repo-Root:  bash scripts/run_full_measurement.sh
#
# Voraussetzungen:
#   - .env mit QWEN_API_KEY / AGENTWORLD_API_KEY (siehe .env.example)
#   - Python mit openai+pyyaml (pip install -e . oder pip install openai pyyaml)
#   - WSL mit git/python3 (fuer Ground-truth-Generierung + hermes Track 1)
#
# HINWEIS: laeuft lange (B ist thinking-schwer, ~9-11k tok/Vorhersage). Einzelne
# Triple-/Task-Fehler killen den Lauf NICHT (fehlertolerant, werden geloggt).
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

echo "==================================================================="
echo " 1/4  Ground truth (Triples) frisch generieren — REAL ausgefuehrt"
echo "==================================================================="
# Terminal-Domaene
for s in terminal_basic errors python textproc git stateful \
         preexisting preexisting2 preexisting3 longchain longchain2; do
  python scripts/gen_triples.py --seq "scripts/seqs/$s.json" --domain terminal \
         --out tasks/terminal/triples --prefix "$s" 2>&1 | grep -E '\->' || true
done
# SWE-Domaene
python scripts/gen_triples.py --seq scripts/seqs/swe.json --domain swe \
       --out tasks/swe/triples --prefix swe 2>&1 | grep -E '\->' || true
echo "Triples: terminal=$(ls tasks/terminal/triples | wc -l)  swe=$(ls tasks/swe/triples | wc -l)"

echo "==================================================================="
echo " 2/4  Track 2 (World Model) — beide Modelle, card-Regime"
echo "      Fixed single judge BEIDE Richtungen (A und B) = vergleichbar"
echo "==================================================================="
python harness/run_track2_worldmodel.py --models A,B --regime card --tasks tasks/ --judge A
python harness/run_track2_worldmodel.py --models A,B --regime card --tasks tasks/ --judge B
# Hinweis: wo --judge A und --judge B uebereinstimmen, ist das Urteil robust.

echo "==================================================================="
echo " 3/4  Track 1 (Policy/hermes) — beide Modelle, alle SWE/Terminal-Tasks"
echo "==================================================================="
python harness/run_track1_policy.py --models A,B --regime greedy --tasks tasks/

echo "==================================================================="
echo " 4/4  Report"
echo "==================================================================="
python scripts/make_report.py results/raw | tee docs/REPORT_AUTO.md
echo "Fertig. Roh-Logs in results/raw/, Auto-Report in docs/REPORT_AUTO.md."
echo "Charts/Analyse: scripts/analyze.py (Token-Effizienz, Head-to-head, je Kategorie)."
