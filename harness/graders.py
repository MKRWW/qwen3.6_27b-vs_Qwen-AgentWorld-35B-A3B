"""Grader: deterministisch (Track 1 Oracles, Track 2 Factuality/Format) + LLM-Judge.

Designprinzip: so viel wie möglich deterministisch messen; LLM-Judge nur für
die subjektiven Track-2-Dimensionen (Consistency/Realism/Quality), mit fixem
Prompt und temp=0. Kein Self-Judging.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

# --------------------------------------------------------------------------- #
# Track 1 — Tool-Call-Validität
# --------------------------------------------------------------------------- #

def grade_tool_call(tc: dict, known_tools: dict[str, dict]) -> dict:
    """Ein einzelner Tool-Call: JSON parsebar? Tool existiert? Pflicht-Args da?"""
    fn = (tc.get("function") or {})
    name = fn.get("name")
    out = {"name": name, "json_ok": False, "tool_known": False, "args_ok": False}
    if name in known_tools:
        out["tool_known"] = True
    try:
        args = json.loads(fn.get("arguments") or "{}")
        out["json_ok"] = True
    except Exception:
        return out
    schema = known_tools.get(name, {})
    required = (schema.get("parameters", {}).get("required") or [])
    out["args_ok"] = all(r in args for r in required)
    return out


# --------------------------------------------------------------------------- #
# Track 2 — deterministische Dimensionen vs. echte Ausführung
# --------------------------------------------------------------------------- #

def _norm(s: str) -> str:
    """Whitespace normalisieren fuer robusteres Matching."""
    return re.sub(r"[ \t]+", " ", (s or "").strip().lower())


def score_factuality(prediction: str, truth: dict) -> dict:
    """Grader v2 — kontinuierlich, vergleicht Vorhersage gegen reale Ausfuehrung.

    Sub-Scores 0..1 (gewichtet -> 'factuality' 0..100):
    - exit_code      : korrekter Exit-Code genannt (falls != 0 immer relevant)
    - stdout_sim     : difflib-Aehnlichkeit (normalisiert) -> Teil-Credit fuer 'fast'
    - stdout_recall  : Anteil echter stdout-Zeilen, die vorkommen
    - stderr_sim     : Aehnlichkeit der Fehlerausgabe (nur falls truth stderr hat)
    - fs_paths       : erwartete neue Dateien/Ordner genannt
    """
    pred = prediction or ""
    pred_n = _norm(pred)
    sub: dict[str, Any] = {}
    weights: dict[str, float] = {}

    exp_exit = truth.get("exit_code")
    if exp_exit is not None:
        # Exit-Code zaehlt staerker bei Fehlern (!=0), wo er diagnostisch ist.
        sub["exit_code"] = 1.0 if re.search(rf"(^|\D){exp_exit}(\D|$)", pred) else 0.0
        weights["exit_code"] = 1.5 if exp_exit != 0 else 0.5

    truth_out = truth.get("stdout") or ""
    if truth_out.strip():
        sub["stdout_sim"] = SequenceMatcher(None, _norm(truth_out), pred_n).ratio()
        weights["stdout_sim"] = 2.0
        lines = [ln for ln in (_norm(truth_out).splitlines()) if ln.strip()]
        if lines:
            hit = sum(1 for ln in lines if ln in pred_n)
            sub["stdout_recall"] = hit / len(lines)
            weights["stdout_recall"] = 1.5

    truth_err = truth.get("stderr") or ""
    if truth_err.strip():
        sub["stderr_sim"] = SequenceMatcher(None, _norm(truth_err), pred_n).ratio()
        weights["stderr_sim"] = 1.5

    paths = list(truth.get("fs_delta") or [])
    if paths:
        hit = sum(1 for p in paths if p.lower() in pred_n)
        sub["fs_paths"] = hit / len(paths)
        weights["fs_paths"] = 1.0

    if not sub:
        # truth ist leer (z.B. erfolgreicher stiller Befehl) -> Modell soll auch leer/knapp sein
        empty_pred = len(pred.strip()) <= 4
        return {"factuality": 100.0 if empty_pred else 40.0,
                "sub": {"empty_expected": 1.0 if empty_pred else 0.0}}

    num = sum(sub[k] * weights[k] for k in sub)
    den = sum(weights[k] for k in sub)
    return {"factuality": round(100 * num / den, 1), "sub": {k: round(v, 3) for k, v in sub.items()}}


def score_format(prediction: str, expected_schema: str | None = None) -> dict:
    """Format-Check. Default: nicht-leer & nicht nur Reasoning-Müll.
    Domänen können `expected_schema` als Regex liefern."""
    pred = prediction or ""
    if not pred.strip():
        return {"format": 0.0, "reason": "leer"}
    if expected_schema:
        ok = bool(re.search(expected_schema, pred, re.S))
        return {"format": 100.0 if ok else 30.0,
                "reason": "schema match" if ok else "schema mismatch"}
    return {"format": 100.0, "reason": "non-empty"}


# --------------------------------------------------------------------------- #
# Track 2 — LLM-Judge (subjektive Dimensionen)
# --------------------------------------------------------------------------- #

JUDGE_SYSTEM = (
    "You are a strict evaluator of world-model predictions. The model was asked to "
    "output ONLY the raw terminal observation (stdout/stderr text + exit code) — "
    "NOT JSON. Do NOT penalize a prediction for being plain text instead of a "
    "structured object; that is the expected format. Compare PREDICTION against the "
    "real outcome (TRUTH) and score three dimensions 0-100:\n"
    "- consistency: does PREDICTION contradict the history/state?\n"
    "- realism: would PREDICTION pass as real terminal output (path/error wording)?\n"
    "- quality: does it capture the correct stdout/stderr/exit content?\n"
    'Respond ONLY with JSON: {"consistency":N,"realism":N,"quality":N,"reason":"..."}'
)


def _truth_as_observation(truth: dict) -> str:
    """truth so darstellen wie das Modell antworten sollte (Roh-Observation), NICHT
    als JSON-Dump — sonst bestraft der Judge Roh-Text faelschlich als 'kein JSON'."""
    parts = []
    if truth.get("stdout"):
        parts.append(truth["stdout"])
    if truth.get("stderr"):
        parts.append(f"[stderr]\n{truth['stderr']}")
    parts.append(f"[exit_code={truth.get('exit_code')}]")
    return "\n".join(parts)


def build_judge_messages(history: Any, action: str, truth: dict, prediction: str) -> list[dict]:
    hist_txt = "\n".join(
        f"$ {h.get('action','')}\n{h.get('observation','')}" for h in (history or [])
    )[:4000]
    user = (
        f"SESSION SO FAR:\n{hist_txt}\n\n"
        f"NEXT ACTION:\n$ {action}\n\n"
        f"REAL OUTCOME (TRUTH):\n{_truth_as_observation(truth)[:4000]}\n\n"
        f"MODEL PREDICTION:\n{(prediction or '')[:4000]}\n"
    )
    return [{"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user}]


def parse_judge(content: str) -> dict:
    """Robustes JSON-Extrahieren aus der Judge-Antwort."""
    m = re.search(r"\{.*\}", content or "", re.S)
    if not m:
        return {"consistency": 0, "realism": 0, "quality": 0, "reason": "unparseable"}
    try:
        d = json.loads(m.group(0))
        for k in ("consistency", "realism", "quality"):
            d[k] = float(d.get(k, 0))
        return d
    except Exception:
        return {"consistency": 0, "realism": 0, "quality": 0, "reason": "json error"}
