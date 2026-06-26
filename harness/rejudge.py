"""Re-judged BEREITS ERZEUGTE Vorhersagen mit einem (neutralen) Judge.

Spart Geld/Zeit: liest predictions aus results/raw/track2_*-Logs, schickt nur die
(truth, prediction)-Paare an den Judge — KEINE teuren Re-Predictions. Ein FIXER
Judge fuer ALLE Modelle => A und B sind direkt vergleichbar.

Aufruf:
  python harness/rejudge.py --judge J --regime card --filter preexisting,longchain,swe
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


def load_triples(tasks_dir: str) -> dict:
    out = {}
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*", "triples", "*.json"))):
        with open(path, encoding="utf-8") as f:
            t = json.load(f)
        out[os.path.relpath(path, tasks_dir)] = t
    return out


def latest_predictions(raw_dir: str, model_key: str, regime: str) -> dict:
    """Neueste prediction-Datei fuer (Modell, Regime) -> {triple_id: prediction}."""
    files = sorted(glob.glob(os.path.join(raw_dir, f"track2_{model_key}_{regime}_*.jsonl")),
                   key=os.path.getmtime)
    preds: dict[str, str] = {}
    for f in files:  # spaetere ueberschreiben fruehere -> neuester Stand gewinnt
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o.get("type") == "result" and "prediction" in o:
                preds[o["triple_id"]] = o["prediction"]
    return preds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="A,B")
    ap.add_argument("--judge", default="J", help="Modell-Key des FIXEN Judges (z.B. J)")
    ap.add_argument("--regime", default="card")
    ap.add_argument("--tasks", default="tasks/")
    ap.add_argument("--raw", default="results/raw")
    ap.add_argument("--filter", default=None, help="nur triple_ids mit diesen Substrings (Komma)")
    ap.add_argument("--max-tokens", type=int, default=512)
    args = ap.parse_args()

    cfg = C.load_config()
    triples = load_triples(args.tasks)
    judge_model = C.get_model(args.judge, cfg)
    subs = [s for s in (args.filter or "").split(",") if s]

    rec = Recorder(track=2, model_key=f"rejudge-{args.judge}", model_id=judge_model.model_id,
                   endpoint=judge_model.endpoint, regime=args.regime,
                   sampling={"note": "rejudge", "judge": args.judge})
    judge_cli = C.make_client(judge_model, C.get_regime("greedy", cfg), recorder=rec,
                              timeout=120.0, max_retries=3)
    print(f"Neutraler Judge: {args.judge} ({judge_model.model_id})")

    agg: dict[str, dict] = {}
    with rec:
        for mk in args.models.split(","):
            preds = latest_predictions(args.raw, mk, args.regime)
            ids = [i for i in sorted(preds) if (not subs or any(s in i for s in subs))]
            dims = {d: [] for d in G.JUDGE_DIMS}
            print(f"\n  Modell {mk}: {len(ids)} Vorhersagen, Judge={args.judge}")
            for tid in ids:
                t = triples.get(tid)
                if not t:
                    continue
                if not (preds[tid] or "").strip():
                    # leere Vorhersage NICHT judgen (Judge halluziniert sonst) -> 0
                    j = {**{d: 0.0 for d in G.JUDGE_DIMS}, "reason": "leere Vorhersage"}
                else:
                    msgs = G.build_judge_messages(t.get("history", []), t["action"],
                                                  t["truth"], preds[tid],
                                                  domain=t.get("domain", "terminal"))
                    try:
                        resp = judge_cli.chat(msgs, max_tokens=args.max_tokens)
                        j = G.parse_judge(C.first_text(resp))
                    except Exception as e:  # noqa: BLE001
                        j = {**{d: None for d in G.JUDGE_DIMS}, "reason": f"err: {e!r}"}
                rec.log_result(triple_id=tid, model=mk, domain=t.get("domain"),
                               judge=j, judge_model=args.judge)
                for d in G.JUDGE_DIMS:
                    if j.get(d) is not None:
                        dims[d].append(j[d])
                short = tid.replace("\\", "/").split("/")[-1].replace(".json", "")
                print(f"    {short:18} F={j.get('factuality')} C={j.get('consistency')} "
                      f"R={j.get('realism')} Q={j.get('quality')}")
            agg[mk] = {d: (round(sum(v) / len(v), 1) if v else None) for d, v in dims.items()}

    print("\n=== Aggregat (FIXER Judge {} -> A vs B vergleichbar) ===".format(args.judge))
    for mk, a in agg.items():
        print(f"  {mk}: " + "  ".join(f"{d}={a[d]}" for d in G.JUDGE_DIMS))
    print(f"\n  Roh-Log: {rec.path}")


if __name__ == "__main__":
    main()
