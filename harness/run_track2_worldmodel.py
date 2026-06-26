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
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import client as C          # noqa: E402
import graders as G         # noqa: E402
from record import Recorder  # noqa: E402

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "config", "prompts")
_PROMPT_CACHE: dict[str, str] = {}


def system_prompt(domain: str) -> str:
    """Offiziellen AgentWorld-Domänen-System-Prompt laden (aus config/prompts/<domain>/).
    So testen wir das Modell mit GENAU dem Prompt, fuer den es trainiert wurde."""
    if domain not in _PROMPT_CACHE:
        path = os.path.join(PROMPT_DIR, domain, "system_prompt.txt")
        with open(path, encoding="utf-8") as f:
            _PROMPT_CACHE[domain] = f.read()
    return _PROMPT_CACHE[domain]


def _user_turn(action: str) -> str:
    # Offizielles Inferenz-Format (Repo-Beispiel): Action: execute_bash\nCommand: <cmd>
    return f"Action: execute_bash\nCommand: {action}"


def _strip_think(text: str) -> str:
    """Falls der Reasoning-Parser den <think>-Block NICHT abtrennt, hier entfernen."""
    return re.sub(r"<think>.*?</think>\s*", "", text or "", flags=re.S).strip()


def build_messages(triple: dict) -> list[dict]:
    """Offizielles Setup: Domänen-System-Prompt + multi-turn (History als echte
    Konversation aus User-Action / Assistant-Observation) + aktuelle Action."""
    msgs = [{"role": "system", "content": system_prompt(triple.get("domain", "terminal"))}]
    for h in triple.get("history", []):
        msgs.append({"role": "user", "content": _user_turn(h.get("action", ""))})
        msgs.append({"role": "assistant", "content": h.get("observation", "")})
    msgs.append({"role": "user", "content": _user_turn(triple["action"])})
    return msgs


def load_triples(tasks_dir: str) -> list[dict]:
    triples = []
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*", "triples", "*.json"))):
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
        t["_id"] = os.path.relpath(path, tasks_dir)
        triples.append(t)
    return triples


def predict(cli: C.Client, triple: dict, max_tokens: int) -> tuple[str, dict]:
    # WICHTIG: Thinking AN (Card: Modell nutzt <think> fuer State-Transitions).
    # enable_thinking NICHT setzen -> Default (an). Reasoning-Parser trennt den
    # think-Block ab; falls nicht, _strip_think() als Fallback.
    resp = cli.chat(build_messages(triple), max_tokens=max_tokens)
    return _strip_think(C.first_text(resp)), resp


def judge(judge_cli: C.Client, triple: dict, prediction: str, max_tokens: int) -> dict:
    msgs = G.build_judge_messages(
        triple.get("history", []), triple["action"], triple["truth"], prediction,
        domain=triple.get("domain", "terminal"))
    # Judge soll NICHT denken (will direktes JSON) -> enable_thinking aus.
    resp = judge_cli.chat(msgs, max_tokens=max_tokens, enable_thinking=False)
    return G.parse_judge(_strip_think(C.first_text(resp)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="A,B")
    ap.add_argument("--regime", default="greedy")
    ap.add_argument("--tasks", default="tasks/")
    ap.add_argument("--filter", default=None, help="nur Triples, deren _id den String enthaelt")
    ap.add_argument("--judge", default=None,
                    help="Judge-Modus: 'none' (nur deterministisch) | 'cross' (jedes "
                         "Modell vom jeweils anderen, NICHT vergleichbar) | <Key> = FIXED "
                         "single judge: dieses eine Modell bewertet ALLE (vergleichbar; "
                         "self-judge-Zeilen werden markiert). Default: none.")
    args = ap.parse_args()

    cfg = C.load_config()
    regime = C.get_regime(args.regime, cfg)
    max_tok = cfg["max_tokens"]["track2_worldmodel"]
    model_keys = args.models.split(",")
    triples = load_triples(args.tasks)
    if args.filter:
        subs = [s for s in args.filter.split(",") if s]
        triples = [t for t in triples if any(s in t["_id"] for s in subs)]
    print(f"{len(triples)} Triples geladen{' (gefiltert: '+args.filter+')' if args.filter else ''}.")

    def pick_judge(model_key: str) -> str | None:
        """Judge-Auswahl:
        - None/'none' -> kein Judge (nur deterministisch).
        - 'cross'     -> das jeweils ANDERE Modell (NICHT vergleichbar, nur Diagnostik).
        - '<Key>'     -> FIXED single judge: dieser eine Key bewertet ALLE Modelle
                         (vergleichbar; self-judge wenn Key==model_key, wird markiert)."""
        if args.judge in (None, "none"):
            return None
        if args.judge == "cross":
            others = [k for k in model_keys if k != model_key]
            return others[0] if others else None
        return args.judge  # fixed single judge fuer alle

    for model_key in model_keys:
        eff_judge_key = pick_judge(model_key)
        model = C.get_model(model_key, cfg)
        rec = Recorder(track=2, model_key=model_key, model_id=model.model_id,
                       endpoint=model.endpoint, regime=regime.name, sampling=regime.params)
        # Timeout grosszuegig: Thinking AN + 32k-Budget -> einzelne Calls koennen
        # >120s dauern (v.a. B remote, oder unter Last). 300s + nur 2 Retries.
        cli = C.make_client(model, regime, recorder=rec, timeout=300.0, max_retries=2)
        judge_cli = None
        if eff_judge_key:
            judge_model = C.get_model(eff_judge_key, cfg)
            judge_cli = C.make_client(judge_model, C.get_regime("greedy", cfg),
                                      recorder=rec, timeout=120.0, max_retries=3)
        self_flag = " (SELF-JUDGE!)" if eff_judge_key == model_key else ""
        print(f"  Modell {model_key}: Judge = {eff_judge_key or 'KEINER (nur deterministisch)'}{self_flag}")

        with rec:
            for t in triples:
                # Fehlertolerant: ein Triple-Fehler (Timeout etc.) killt nicht den Lauf.
                try:
                    prediction, _ = predict(cli, t, max_tok)
                    fact = G.score_factuality(prediction, t["truth"])
                    fmt = G.score_format(prediction, t.get("format_schema"))
                    jdg = judge(judge_cli, t, prediction, max_tok) if judge_cli else None
                    rec.log_result(
                        triple_id=t["_id"], domain=t.get("domain"),
                        prediction=prediction, factuality=fact, format=fmt, judge=jdg,
                        judge_model=eff_judge_key,
                    )
                    print(f"  [{model_key}] {t['_id']}: fact={fact['factuality']} "
                          f"fmt={fmt['format']}" + (f" judge={jdg}" if jdg else ""))
                except Exception as e:  # noqa: BLE001 - bench: log & continue
                    rec.log_result(triple_id=t["_id"], domain=t.get("domain"),
                                   error=repr(e))
                    print(f"  [{model_key}] {t['_id']}: FEHLER -> {e!r} (uebersprungen)")
        print(f"  -> {rec.path}")


if __name__ == "__main__":
    main()
