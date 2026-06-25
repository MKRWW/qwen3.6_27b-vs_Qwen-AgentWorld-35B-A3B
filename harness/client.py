"""Dünner OpenAI-kompatibler Client mit Retry, Timeout und vollem Logging.

Beide Modelle (A=Qwen3.6, B=AgentWorld) sprechen die OpenAI-Chat-API. Dieser
Wrapper kapselt Endpoint-Wahl, Sampling-Regime und das verpflichtende JSONL-Logging
jedes Requests/Responses (siehe harness/record.py).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import yaml
from openai import OpenAI

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "models.yaml")


@dataclass
class ModelSpec:
    key: str            # "A" | "B"
    name: str
    endpoint: str
    model_id: str
    api_key: str
    quant: str
    notes: str = ""


@dataclass
class SamplingRegime:
    name: str           # "greedy" | "card"
    params: dict[str, Any] = field(default_factory=dict)


def load_dotenv(path: str | None = None) -> None:
    """Minimaler .env-Loader (keine Extra-Dependency). Setzt nur fehlende Keys."""
    path = path or os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


def load_config(path: str = CONFIG_PATH) -> dict:
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_model(key: str, cfg: dict | None = None) -> ModelSpec:
    cfg = cfg or load_config()
    m = cfg["models"][key]
    api_key = os.environ.get(m["api_key_env"], "")
    if not api_key:
        raise RuntimeError(
            f"API-Key env '{m['api_key_env']}' für Modell {key} nicht gesetzt. "
            f"Siehe .env.example."
        )
    return ModelSpec(
        key=key, name=m["name"], endpoint=m["endpoint"], model_id=m["model_id"],
        api_key=api_key, quant=m.get("quant", "?"), notes=m.get("notes", ""),
    )


def get_regime(name: str, cfg: dict | None = None) -> SamplingRegime:
    cfg = cfg or load_config()
    return SamplingRegime(name=name, params=dict(cfg["sampling_regimes"][name]))


class Client:
    """Ein Modell + ein Sampling-Regime. Loggt jeden Call über `recorder`."""

    def __init__(self, model: ModelSpec, regime: SamplingRegime, recorder=None,
                 timeout: float = 120.0, max_retries: int = 3):
        self.model = model
        self.regime = regime
        self.recorder = recorder
        self.max_retries = max_retries
        self._oai = OpenAI(base_url=model.endpoint, api_key=model.api_key,
                           timeout=timeout, max_retries=0)

    def chat(self, messages: list[dict], *, max_tokens: int,
             tools: list[dict] | None = None, tool_choice: Any = None,
             enable_thinking: bool | None = None,
             extra: dict | None = None) -> dict:
        """Ein Chat-Completion-Call. Gibt das rohe Response-Dict zurück und loggt alles.

        enable_thinking: bei Qwen3-Modellen Reasoning-Block an/aus (chat_template_kwargs).
        Für Track 2 (Next-State-Simulation) auf False -> direkte Observation statt
        Gedankenkette (sonst frisst <think> das Token-Budget -> leerer content).
        """
        # top_k / chat_template_kwargs sind keine Standard-OpenAI-Params -> via extra_body.
        params: dict[str, Any] = {
            "model": self.model.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        sp = dict(self.regime.params)
        extra_body: dict[str, Any] = {}
        for k in ("temperature", "top_p", "seed"):
            if k in sp:
                params[k] = sp[k]
        if "top_k" in sp:
            extra_body["top_k"] = sp["top_k"]
        if enable_thinking is not None:
            extra_body["chat_template_kwargs"] = {"enable_thinking": enable_thinking}
        if tools:
            params["tools"] = tools
            if tool_choice is not None:
                params["tool_choice"] = tool_choice
        if extra:
            params.update(extra)
        if extra_body:
            params["extra_body"] = extra_body

        last_err = None
        for attempt in range(1, self.max_retries + 1):
            t0 = time.monotonic()
            try:
                resp = self._oai.chat.completions.create(**params)
                dt = time.monotonic() - t0
                data = resp.model_dump()
                self._log(params, data, dt, attempt, error=None)
                return data
            except Exception as e:  # noqa: BLE001 - bench harness, log & retry
                dt = time.monotonic() - t0
                last_err = e
                self._log(params, None, dt, attempt, error=repr(e))
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"chat() nach {self.max_retries} Versuchen gescheitert: {last_err}")

    def _log(self, request, response, latency_s, attempt, error):
        if self.recorder is None:
            return
        self.recorder.log_call(
            model_key=self.model.key, model_id=self.model.model_id,
            endpoint=self.model.endpoint, regime=self.regime.name,
            request=request, response=response, latency_s=latency_s,
            attempt=attempt, error=error,
        )


def first_text(response: dict) -> str:
    """content extrahieren; reasoning_content getrennt behandeln (leerer content = Flag)."""
    try:
        return response["choices"][0]["message"].get("content") or ""
    except Exception:
        return ""


def tool_calls(response: dict) -> list[dict]:
    try:
        return response["choices"][0]["message"].get("tool_calls") or []
    except Exception:
        return []


def finish_reason(response: dict) -> str | None:
    try:
        return response["choices"][0].get("finish_reason")
    except Exception:
        return None
