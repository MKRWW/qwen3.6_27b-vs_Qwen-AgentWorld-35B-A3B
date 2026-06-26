#!/usr/bin/env bash
# VOLLMESSUNG (sauberer State) mit Replikaten + neutralem Judge.
# Aufruf aus dem Repo-Root:  bash scripts/run_full_measurement.sh [REPS]
#   REPS = Anzahl Replikate (Default 3) -> Mittelwert +/- Spannweite (Varianz).
#
# Vorhersagen laufen auf EIGENER Infra (zuse+vast) -> 0 EUR. Nur der neutrale
# Judge J (OpenRouter/mistral-small) kostet echtes Geld (~$0.05 gesamt).
# Fehlertolerant: einzelne Timeouts (A denkt manchmal lang) killen den Lauf NICHT.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
REPS="${1:-3}"

echo "###################################################################"
echo "# 0/4  Sauberer State: alte Roh-Logs weg, Triples frisch generieren"
echo "###################################################################"
rm -f results/raw/*.jsonl
rm -f tasks/terminal/triples/*.json tasks/swe/triples/*.json
for s in terminal_basic errors python textproc git stateful \
         preexisting preexisting2 preexisting3 longchain longchain2; do
  python scripts/gen_triples.py --seq "scripts/seqs/$s.json" --domain terminal \
         --out tasks/terminal/triples --prefix "$s" >/dev/null 2>&1
done
python scripts/gen_triples.py --seq scripts/seqs/swe.json --domain swe \
       --out tasks/swe/triples --prefix swe >/dev/null 2>&1
echo "Triples: terminal=$(ls tasks/terminal/triples | wc -l)  swe=$(ls tasks/swe/triples | wc -l)"

echo "###################################################################"
echo "# 1/4  Track 2 (World Model) — $REPS Replikate, card-Regime, Judge=J"
echo "#      predict (gratis, eigene GPUs) + neutraler Judge J (vergleichbar)"
echo "###################################################################"
for r in $(seq 1 "$REPS"); do
  echo "----- Track 2 Replikat $r/$REPS -----"
  python harness/run_track2_worldmodel.py --models A,B --regime card --tasks tasks/ --judge J
done

echo "###################################################################"
echo "# 2/4  Track 1 (Policy/hermes) — $REPS Replikate, alle SWE-Tasks"
echo "###################################################################"
for r in $(seq 1 "$REPS"); do
  echo "----- Track 1 Replikat $r/$REPS -----"
  python harness/run_track1_policy.py --models A,B --regime greedy --tasks tasks/
done

echo "###################################################################"
echo "# 3/4  Aggregation"
echo "###################################################################"
python scripts/make_report.py results/raw | tee docs/REPORT_AUTO.md
python scripts/analyze.py results/raw --json docs/data/summary.json | tee docs/ANALYSIS_AUTO.md

echo "###################################################################"
echo "# 4/4  FERTIG"
echo "###################################################################"
echo "Roh-Logs: results/raw/  |  Report: docs/REPORT_AUTO.md  |  Analyse: docs/ANALYSIS_AUTO.md"
echo "Replikate je Modell sind separate Dateien -> analyze/make_report zeigen sie als Zeilen."
