"""Track 2 — World-Model-Fidelity.

Für jedes (history, action, truth)-Triple lassen wir das Modell den nächsten
Zustand vorhersagen und scoren Vorhersage vs. echte Ausführung.

Triples liegen als JSON in tasks/<domain>/triples/*.json (Schema siehe
tasks/README.md). Ground truth wird offline via scripts/gen_triples.py erzeugt
(echte Befehle in WSL-Sandbox ausführen) — dieser Runner liest sie nur.

Aufruf:
  python harness/run_track2_worldmodel.py --models A,B --regime greedy \
         --tasks tasks/ --judge A
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import client as C          # noqa: E402
import graders as G         # noqa: E402
from record import Recorder  # noqa: E402

# Domänen-spezifisches System-Prompt (Card empfiehlt eigene Prompts pro Domäne).
# Platzhalter — finale Prompts aus dem AgentWorld-GitHub übernehmen.
SYSTEM_BY_DOMAIN = {
    "terminal": (
        "You are a world model simulating a Linux shell. Given the session history "
        "and the next command, output ONLY the resulting terminal observation "
        "(stdout/stderr and the resulting exit code). Do not explain."
    ),
    "swe": (
        "You are a world model simulating a software repository. Given the repo "
        "history and the next action, output ONLY the resulting observation "
        "(command output / test results / file state). Do not explain."
    ),
}


def load_triples(tasks_dir: str) -> list[dict]:
    triples = []
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*", "triples", "*.json"))):
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
        t["_id"] = os.path.relpath(path, tasks_dir)
        triples.append(t)
    return triples


def predict(cli: C.Client, triple: dict, max_tokens: int) -> tuple[str, dict]:
    domain = triple.get("domain", "terminal")
    msgs = [
        {"role": "system", "content": SYSTEM_BY_DOMAIN.get(domain, SYSTEM_BY_DOMAIN["terminal"])},
        {"role": "user", "content": json.dumps(
            {"history": triple.get("history", []), "action": triple["action"]},
            ensure_ascii=False)},
    ]
    resp = cli.chat(msgs, max_tokens=max_tokens)
    return C.first_text(resp), resp


def judge(judge_cli: C.Client, triple: dict, prediction: str, max_tokens: int) -> dict:
    msgs = G.build_judge_messages(
        triple.get("history", []), triple["action"], triple["truth"], prediction)
    resp = judge_cli.chat(msgs, max_tokens=max_tokens)
    return G.parse_judge(C.first_text(resp))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="A,B")
    ap.add_argument("--regime", default="greedy")
    ap.add_argument("--tasks", default="tasks/")
    ap.add_argument("--judge", default=None, help="Modell-Key des Judges (kein Self-Judging)")
    args = ap.parse_args()

    cfg = C.load_config()
    regime = C.get_regime(args.regime, cfg)
    max_tok = cfg["max_tokens"]["track2_worldmodel"]
    judge_key = args.judge or cfg["judge"]["default"]
    triples = load_triples(args.tasks)
    print(f"{len(triples)} Triples geladen.")

    for model_key in args.models.split(","):
        if model_key == judge_key:
            print(f"  Hinweis: Judge={judge_key} == Prüfling {model_key} -> Self-Judging "
                  f"vermieden, nutze alternativen Judge.")
        eff_judge_key = cfg["judge"]["alt"] if model_key == judge_key else judge_key

        model = C.get_model(model_key, cfg)
        rec = Recorder(track=2, model_key=model_key, model_id=model.model_id,
                       endpoint=model.endpoint, regime=regime.name, sampling=regime.params)
        cli = C.Client(model, regime, recorder=rec)
        judge_model = C.get_model(eff_judge_key, cfg)
        judge_cli = C.Client(judge_model, C.get_regime("greedy", cfg), recorder=rec)

        with rec:
            for t in triples:
                prediction, _ = predict(cli, t, max_tok)
                fact = G.score_factuality(prediction, t["truth"])
                fmt = G.score_format(prediction, t.get("format_schema"))
                jdg = judge(judge_cli, t, prediction, max_tok)
                rec.log_result(
                    triple_id=t["_id"], domain=t.get("domain"),
                    prediction=prediction, factuality=fact, format=fmt, judge=jdg,
                    judge_model=eff_judge_key,
                )
                print(f"  [{model_key}] {t['_id']}: fact={fact['factuality']} "
                      f"fmt={fmt['format']} judge={jdg}")
        print(f"  -> {rec.path}")


if __name__ == "__main__":
    main()
