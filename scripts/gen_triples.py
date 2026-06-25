"""Erzeugt World-Model-Triples mit ECHTER Ground truth aus einer WSL-Sandbox.

Liest eine Aktions-Sequenz (JSON-Liste von Shell-Befehlen), fuehrt sie Schritt
fuer Schritt in einem frischen WSL-tmp-Verzeichnis aus und schreibt pro Schritt
ein Triple { history, action, truth } nach tasks/<domain>/triples/.

So ist `truth` garantiert real (nie geraten) -> Anti-Kontamination + Fairness.

Aufruf:
  python scripts/gen_triples.py --seq scripts/seqs/terminal_basic.json \
         --domain terminal --out tasks/terminal/triples
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess


def wsl(cmd: str, cwd_wsl: str, timeout: int = 60) -> dict:
    full = f"cd '{cwd_wsl}' && {cmd}; echo \"__EXIT__$?\""
    proc = subprocess.run(["wsl.exe", "-e", "bash", "-lc", full],
                          capture_output=True, text=True, timeout=timeout)
    out = proc.stdout
    exit_code = 0
    if "__EXIT__" in out:
        out, _, tail = out.rpartition("__EXIT__")
        try:
            exit_code = int(tail.strip().splitlines()[0])
        except Exception:
            exit_code = proc.returncode
    return {"stdout": out.rstrip("\n"), "stderr": proc.stderr.rstrip("\n"),
            "exit_code": exit_code}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", required=True, help="JSON-Liste von Shell-Befehlen")
    ap.add_argument("--domain", default="terminal")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.seq, encoding="utf-8") as f:
        actions = json.load(f)

    # frische WSL-Sandbox
    mk = subprocess.run(["wsl.exe", "-e", "bash", "-lc", "mktemp -d"],
                        capture_output=True, text=True)
    sandbox = mk.stdout.strip()
    print(f"WSL-Sandbox: {sandbox}")
    os.makedirs(args.out, exist_ok=True)

    history = []
    try:
        for i, action in enumerate(actions):
            before = wsl("ls -1A 2>/dev/null", sandbox)["stdout"].splitlines()
            res = wsl(action, sandbox)
            after = wsl("ls -1A 2>/dev/null", sandbox)["stdout"].splitlines()
            fs_delta = sorted(set(after) - set(before))
            triple = {
                "domain": args.domain,
                "history": list(history),
                "action": action,
                "truth": {**res, "fs_delta": fs_delta},
                "format_schema": None,
            }
            out_path = os.path.join(args.out, f"seq_{i:02d}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(triple, f, ensure_ascii=False, indent=2)
            print(f"  -> {out_path}  exit={res['exit_code']} delta={fs_delta}")
            history.append({"action": action, "observation": res["stdout"]})
    finally:
        subprocess.run(["wsl.exe", "-e", "bash", "-lc", f"rm -rf '{sandbox}'"])
        print("Sandbox entfernt.")


if __name__ == "__main__":
    main()
