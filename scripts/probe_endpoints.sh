#!/usr/bin/env bash
# Connectivity- + Capability-Probe für beide Endpoints.
# Klärt: erreichbar? welche model_id? Tool-Call-Parser aktiv? Reasoning leer?
# Nutzung:  ./scripts/probe_endpoints.sh   (lädt .env wenn vorhanden)
set -uo pipefail

[ -f .env ] && set -a && . ./.env && set +a

QWEN_BASE="http://192.168.178.21:8000/v1"
AW_BASE="http://194.228.55.129:37773/v1"

hr() { printf '%.0s=' {1..70}; echo; }

probe() {
  local name="$1" base="$2" key="$3"
  hr; echo "### $name  ($base)"; hr
  echo "--- /models ---"
  curl -s -m 8 -H "Authorization: Bearer ${key}" "$base/models" \
    | python3 -m json.tool 2>/dev/null || echo "  (keine/ungültige Antwort — Token? erreichbar?)"

  echo "--- minimal chat (leerer-content-Check) ---"
  curl -s -m 30 -H "Authorization: Bearer ${key}" -H "Content-Type: application/json" \
    "$base/chat/completions" -d '{
      "model": "MODEL_PLACEHOLDER",
      "messages": [{"role":"user","content":"Reply with the single word: pong"}],
      "max_tokens": 256, "temperature": 0
    }' | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    c = d["choices"][0]
    msg = c.get("message", {})
    print("  finish_reason:", c.get("finish_reason"))
    print("  content_len  :", len(msg.get("content") or ""))
    print("  content      :", repr((msg.get("content") or "")[:120]))
    print("  has_reasoning:", bool(msg.get("reasoning_content")))
    print("  usage        :", d.get("usage"))
except Exception as e:
    print("  parse error:", e); print(sys.stdin.read()[:300])
'

  echo "--- tool-calling support check ---"
  curl -s -m 30 -H "Authorization: Bearer ${key}" -H "Content-Type: application/json" \
    "$base/chat/completions" -d '{
      "model": "MODEL_PLACEHOLDER",
      "messages": [{"role":"user","content":"What is 12 times 7? Use the calculator tool."}],
      "tools": [{"type":"function","function":{"name":"calculator",
        "description":"Evaluate an arithmetic expression",
        "parameters":{"type":"object","properties":{"expr":{"type":"string"}},"required":["expr"]}}}],
      "tool_choice": "auto", "max_tokens": 256, "temperature": 0
    }' | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    c = d["choices"][0]["message"]
    tc = c.get("tool_calls")
    if tc:
        print("  TOOL-CALLS: OK ->", tc[0]["function"]["name"], tc[0]["function"]["arguments"][:80])
    else:
        print("  TOOL-CALLS: NONE (Parser evtl. nicht aktiv) content:", repr((c.get(\"content\") or \"\")[:120]))
except Exception as e:
    print("  parse error:", e)
'
  echo
}

echo "HINWEIS: ersetze MODEL_PLACEHOLDER unten mit der model_id aus /models,"
echo "oder exportiere QWEN_MODEL / AW_MODEL und passe das Skript an."
echo

probe "Qwen3.6-27b" "$QWEN_BASE" "${QWEN_API_KEY:-dummy}"
probe "AgentWorld-35B-A3B" "$AW_BASE" "${AGENTWORLD_API_KEY:-}"

hr
echo "Nächster Schritt: model_id von B in config/models.yaml eintragen."
