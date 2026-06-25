"""Grader: deterministisch (Track 1 Oracles, Track 2 Factuality/Format) + LLM-Judge.

Designprinzip: so viel wie möglich deterministisch messen; LLM-Judge nur für
die subjektiven Track-2-Dimensionen (Consistency/Realism/Quality), mit fixem
Prompt und temp=0. Kein Self-Judging.
"""
from __future__ import annotations

import json
import re
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

def score_factuality(prediction: str, truth: dict) -> dict:
    """Vergleicht die Vorhersage gegen reale (stdout, exit_code, fs_delta).

    Liefert Sub-Scores 0..1; Aggregat als 'factuality'. Bewusst simpel & prüfbar:
    - exit_code muss exakt erwähnt/korrekt sein, wenn relevant
    - Schlüssel-Zeilen aus echtem stdout müssen vorkommen (fuzzy, zeilenweise)
    - erwartete Dateipfade aus fs_delta müssen genannt sein
    """
    pred = prediction or ""
    pred_l = pred.lower()
    sub: dict[str, Any] = {}

    # exit code
    exp_exit = truth.get("exit_code")
    if exp_exit is not None:
        sub["exit_code"] = 1.0 if re.search(rf"\b{exp_exit}\b", pred) else 0.0

    # stdout key lines
    truth_lines = [ln.strip() for ln in (truth.get("stdout") or "").splitlines() if ln.strip()]
    if truth_lines:
        hit = sum(1 for ln in truth_lines if ln.lower() in pred_l)
        sub["stdout_recall"] = hit / len(truth_lines)

    # fs delta paths
    paths = [p for p in (truth.get("fs_delta") or [])]
    if paths:
        hit = sum(1 for p in paths if p.lower() in pred_l)
        sub["fs_paths"] = hit / len(paths)

    vals = list(sub.values())
    factuality = sum(vals) / len(vals) if vals else 0.0
    return {"factuality": round(100 * factuality, 1), "sub": sub}


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
    "You are a strict evaluator of world-model predictions. Given the real "
    "environment outcome (TRUTH) and a model's PREDICTION of that outcome, score "
    "three dimensions from 0 to 100. Be conservative; reward only genuine matches.\n"
    "- consistency: does PREDICTION contradict the provided history/state?\n"
    "- realism: would PREDICTION pass as a real environment output (path formats, "
    "error wording, structure)?\n"
    "- quality: completeness and usefulness as a faithful next-state.\n"
    'Respond ONLY with JSON: {"consistency":N,"realism":N,"quality":N,"reason":"..."}'
)


def build_judge_messages(history: Any, action: str, truth: dict, prediction: str) -> list[dict]:
    user = (
        f"HISTORY:\n{json.dumps(history, ensure_ascii=False)[:4000]}\n\n"
        f"ACTION:\n{action}\n\n"
        f"TRUTH:\n{json.dumps(truth, ensure_ascii=False)[:4000]}\n\n"
        f"PREDICTION:\n{prediction[:4000]}\n"
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
