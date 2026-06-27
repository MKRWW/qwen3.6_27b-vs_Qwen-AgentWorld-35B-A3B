"""Erzeugt die Track-3-Closed-Loop-Tasks unter tasks/closedloop/<name>/.

Jeder Task = { task.json (goal, max_steps), setup.sh (seedet relative Dateien),
oracle.sh (exit 0 = geloest) }. Determinismus + RELATIVE Pfade sind Pflicht
(siehe docs/TRACK3_PLAN.md: ein zufaelliger tmp-Pfad/pwd waere fuer das Sim-Modell
nicht vorhersagbar -> triviale Divergenz). Start-Zustand MUSS oracle FAILen lassen
(sonst diskriminiert der Oracle nicht).

Aufruf:  python scripts/make_closedloop_tasks.py
"""
from __future__ import annotations

import json
import os
import stat

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(HERE, "tasks", "closedloop")

# Jeder Task: setup (seed), goal (an die Policy), oracle (Bash, exit 0 = geloest),
# max_steps. Tasks sind so gewaehlt, dass ein GENERISCHER Befehl sie real loest
# (grep/sort/awk/wc) — haengt der Agent dagegen an HALLUZINIERTEM Sim-Inhalt fest
# (z. B. `echo <erfundene Zeile>`), scheitert der Real-Replay -> genau das messen wir.
TASKS = [
    {
        "name": "create_file",
        "goal": "Create a file named greeting.txt whose only content is the exact "
                "single line: hello world",
        "setup": "",
        "oracle": 'test -f greeting.txt && [ "$(cat greeting.txt)" = "hello world" ]',
        "max_steps": 6,
    },
    {
        "name": "count_lines",
        "goal": "The file data.txt contains several lines. Write the number of lines "
                "in data.txt (just the integer, nothing else) into a file count.txt.",
        "setup": "printf 'alpha\\nbeta\\ngamma\\ndelta\\nepsilon\\n' > data.txt",
        "oracle": '[ "$(cat count.txt 2>/dev/null)" = "5" ]',
        "max_steps": 6,
    },
    {
        "name": "rename_file",
        "goal": "Rename the file old.txt to new.txt (the file old.txt must no longer "
                "exist, new.txt must exist with the same content).",
        "setup": "printf 'payload-content\\n' > old.txt",
        "oracle": 'test -f new.txt && [ ! -e old.txt ] && '
                  '[ "$(cat new.txt)" = "payload-content" ]',
        "max_steps": 6,
    },
    {
        "name": "append_line",
        "goal": "Append a new last line containing exactly DONE to the file log.txt, "
                "without changing the existing lines.",
        "setup": "printf 'alpha\\nbeta\\n' > log.txt",
        "oracle": '[ "$(sed -n 1p log.txt)" = "alpha" ] && '
                  '[ "$(sed -n 2p log.txt)" = "beta" ] && '
                  '[ "$(sed -n 3p log.txt)" = "DONE" ] && '
                  '[ "$(wc -l < log.txt)" -eq 3 ]',
        "max_steps": 6,
    },
    {
        "name": "mkdir_move",
        "goal": "Create a directory named backup and move the file notes.txt into it "
                "(so backup/notes.txt exists and ./notes.txt no longer does).",
        "setup": "printf 'remember the milk\\n' > notes.txt",
        "oracle": 'test -f backup/notes.txt && [ ! -e notes.txt ] && '
                  '[ "$(cat backup/notes.txt)" = "remember the milk" ]',
        "max_steps": 6,
    },
    {
        "name": "grep_filter",
        "goal": "Write every line of words.txt that contains the word apple into a new "
                "file apples.txt, preserving their original order.",
        "setup": "printf 'apple pie\\nbanana\\ngreen apple\\ncherry\\napple\\n' > words.txt",
        "oracle": '[ "$(cat apples.txt 2>/dev/null)" = '
                  '"$(printf \'apple pie\\ngreen apple\\napple\')" ]',
        "max_steps": 7,
    },
    {
        "name": "sum_numbers",
        "goal": "The file nums.txt has one integer per line. Compute their sum and "
                "write only the resulting number into sum.txt.",
        "setup": "printf '3\\n7\\n10\\n5\\n' > nums.txt",
        "oracle": '[ "$(cat sum.txt 2>/dev/null)" = "25" ]',
        "max_steps": 7,
    },
    {
        "name": "sort_unique",
        "goal": "Create a file sorted_unique.txt containing the lines of names.txt "
                "sorted alphabetically (ascending) with duplicate lines removed.",
        "setup": "printf 'charlie\\nalice\\nbob\\nalice\\ncharlie\\n' > names.txt",
        "oracle": '[ "$(cat sorted_unique.txt 2>/dev/null)" = '
                  '"$(printf \'alice\\nbob\\ncharlie\')" ]',
        "max_steps": 7,
    },
]


def _w(path: str, content: str, executable: bool = False) -> None:
    # LF-Zeilenenden erzwingen (laeuft in WSL/bash; CRLF wuerde `\r` einschleppen).
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


def main() -> None:
    for t in TASKS:
        d = os.path.join(ROOT, t["name"])
        os.makedirs(d, exist_ok=True)
        _w(os.path.join(d, "task.json"), json.dumps(
            {"name": t["name"], "goal": t["goal"], "domain": "terminal",
             "max_steps": t["max_steps"]}, ensure_ascii=False, indent=2) + "\n")
        setup = "#!/usr/bin/env bash\nset -e\n" + (t["setup"] + "\n" if t["setup"] else "")
        _w(os.path.join(d, "setup.sh"), setup, executable=True)
        oracle = ("#!/usr/bin/env bash\n# exit 0 = task solved. Runs in the sandbox cwd.\n"
                  + t["oracle"] + "\n")
        _w(os.path.join(d, "oracle.sh"), oracle, executable=True)
        print(f"  tasks/closedloop/{t['name']}/  (max_steps={t['max_steps']})")
    print(f"{len(TASKS)} Tasks geschrieben -> {ROOT}")


if __name__ == "__main__":
    main()
