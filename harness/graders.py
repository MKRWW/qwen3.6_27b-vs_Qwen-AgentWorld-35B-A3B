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


def _line_recall(truth_text: str, pred_n: str) -> tuple[float, int]:
    """Anteil der (normalisierten, nicht-leeren) Wahrheits-Zeilen, die im
    vorhergesagten Screen vorkommen. Robust gegen Prompt-/Echo-Beiwerk."""
    lines = [ln for ln in _norm(truth_text).splitlines() if ln.strip()]
    if not lines:
        return 1.0, 0
    hit = sum(1 for ln in lines if ln in pred_n)
    return hit / len(lines), len(lines)


def score_factuality(prediction: str, truth: dict) -> dict:
    """Grader v3 — fair fuer das offizielle Terminal-SCREEN-Format.

    Das Modell gibt den ganzen Screen aus (Prompt + Command-Echo + Output + neuer
    Prompt). Exit-Code und fs-Delta sind im Screen NICHT sichtbar -> wir bewerten
    nur die wirklich sichtbare Ausgabe: Recall ueber echte stdout- + stderr-Zeilen.
    Falscher Output -> Zeile fehlt -> Recall < 1 (diskriminiert weiter); korrektes
    Screen-Format wird NICHT bestraft.
    """
    pred = prediction or ""
    pred_n = _norm(pred)
    out_recall, n_out = _line_recall(truth.get("stdout") or "", pred_n)
    err_recall, n_err = _line_recall(truth.get("stderr") or "", pred_n)

    # truth ohne sichtbare Ausgabe (stiller Erfolg): Screen soll nur Prompt+Command
    # zeigen, keine erfundene Ausgabe/Fehler.
    if n_out == 0 and n_err == 0:
        spurious = bool(re.search(r"error|traceback|no such file|not found|denied", pred_n))
        return {"factuality": 30.0 if spurious else 100.0,
                "sub": {"silent_success": 0.0 if spurious else 1.0}}

    num = out_recall * (2.0 if n_out else 0) + err_recall * (1.5 if n_err else 0)
    den = (2.0 if n_out else 0) + (1.5 if n_err else 0)
    return {"factuality": round(100 * num / den, 1),
            "sub": {"stdout_recall": round(out_recall, 3) if n_out else None,
                    "stderr_recall": round(err_recall, 3) if n_err else None}}


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
