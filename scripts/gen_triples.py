"""Erzeugt World-Model-Triples mit ECHTER Ground truth aus EINER persistenten
WSL-Shell-Session (cwd/env/Variablen bleiben erhalten, wie in einem echten
Terminal).

Liest eine Aktions-Sequenz (JSON-Liste von Shell-Befehlen), fuehrt sie in genau
einer bash-Session aus und schreibt pro Schritt ein Triple { history, action,
truth }. `truth` ist garantiert real (nie geraten) -> Anti-Kontamination + Fairness.

Aufruf:
  python scripts/gen_triples.py --seq scripts/seqs/terminal_basic.json \
         --domain terminal --out tasks/terminal/triples
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess

MARK = "@@STEP@@"


def build_driver(sandbox: str, actions: list[str]) -> str:
    """Ein bash-Skript, das ALLE Aktionen in derselben Session ausfuehrt und pro
    Schritt eine maschinenlesbare Marker-Zeile emittiert (base64, newline-sicher)."""
    # WICHTIG: die Action darf NICHT in $(...) laufen (Subshell -> cd/export gehen
    # verloren). Stattdessen Brace-Group mit Datei-Redirect im aktuellen Shell-Kontext.
    # Temp-Dateien liegen in /tmp, damit sie nicht im sandbox-`ls` auftauchen.
    lines = ["set +e", f"cd '{sandbox}'"]
    for i, action in enumerate(actions):
        o, e = f"/tmp/__o.$$.{i}", f"/tmp/__e.$$.{i}"
        lines += [
            "____before=$(ls -1A 2>/dev/null)",
            f"{{ {action} ; }} > {o} 2> {e} ; ____ec=$?",   # current shell -> cd persistiert
            f"____out=$(cat {o}); ____err=$(cat {e}); rm -f {o} {e}",
            "____after=$(ls -1A 2>/dev/null)",
            "____delta=$(comm -13 <(echo \"$____before\"|sort) <(echo \"$____after\"|sort))",
            f"echo \"{MARK}{i}|$(echo -n \"$____out\"|base64 -w0)|$(echo -n \"$____err\"|base64 -w0)"
            f"|$____ec|$(echo -n \"$(pwd)\"|base64 -w0)|$(echo -n \"$____delta\"|base64 -w0)\"",
        ]
    return "\n".join(lines)


def b64d(s: str) -> str:
    if not s:
        return ""
    return base64.b64decode(s).decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True, help="JSON-Liste von Shell-Befehlen")
    ap.add_argument("--domain", default="terminal")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.seq, encoding="utf-8") as f:
        actions = json.load(f)

    sandbox = subprocess.run(["wsl.exe", "-e", "bash", "-lc", "mktemp -d"],
                             capture_output=True, text=True).stdout.strip()
    print(f"WSL-Sandbox (persistente Session): {sandbox}")
    os.makedirs(args.out, exist_ok=True)

    driver = build_driver(sandbox, actions)
    proc = subprocess.run(["wsl.exe", "-e", "bash", "-lc", driver],
                          capture_output=True, text=True, timeout=300)

    steps = {}
    for line in proc.stdout.splitlines():
        if not line.startswith(MARK):
            continue
        body = line[len(MARK):]
        idx, out_b, err_b, ec, pwd_b, delta_b = body.split("|")
        steps[int(idx)] = {
            "stdout": b64d(out_b), "stderr": b64d(err_b), "exit_code": int(ec),
            "cwd": b64d(pwd_b),
            "fs_delta": [x for x in b64d(delta_b).splitlines() if x.strip()],
        }

    history = []
    for i, action in enumerate(actions):
        s = steps.get(i)
        if s is None:
            print(f"  WARN: Schritt {i} ohne Marker (Befehl gescheitert?) -> uebersprungen")
            continue
        triple = {
            "domain": args.domain,
            "history": list(history),
            "action": action,
            "truth": {"stdout": s["stdout"], "stderr": s["stderr"],
                      "exit_code": s["exit_code"], "cwd": s["cwd"],
                      "fs_delta": s["fs_delta"]},
            "format_schema": None,
        }
        out_path = os.path.join(args.out, f"seq_{i:02d}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(triple, f, ensure_ascii=False, indent=2)
        print(f"  -> seq_{i:02d}.json  exit={s['exit_code']} cwd={s['cwd']} "
              f"delta={s['fs_delta']} stdout={s['stdout']!r}")
        history.append({"action": action, "observation": s["stdout"]})

    subprocess.run(["wsl.exe", "-e", "bash", "-lc", f"rm -rf '{sandbox}'"])
    print("Sandbox entfernt.")


if __name__ == "__main__":
    main()
