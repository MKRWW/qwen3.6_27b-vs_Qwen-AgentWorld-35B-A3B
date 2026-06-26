"""Erzeugt den LANGHORIZONT-BRUTAL-Test unter tasks/longhorizon/.

Im Gegensatz zur closedloop-Suite (kurz, mit umgebungs-agnostischen One-Linern lösbar)
ZWINGEN diese Tasks den Agenten, **halluzinierbaren Inhalt zu lesen und darauf eine
literale, schwer-skriptbare Entscheidung zu treffen** — genau dort sollte sich Per-Step-
Divergenz in Real-Replay-Versagen + Täuschung übersetzen, falls die Aufschaukel-Hypothese
stimmt. Mechanismen:
  * semantisches Verdikt (Erfolg/Fehlschlag aus einem Log ableiten -> literales Wort),
  * Mehr-Hop-Kette (7 Reads, B muss über viele Turns selbst-konsistent bleiben),
  * Verifikations-Schleife (B's halluziniertes Erfolgssignal -> Agent glaubt fertig),
  * Transkription eines entdeckten Werts an eine nicht-ableitbare Stelle,
  * bedingte Verteilung (gelesener Status entscheidet, WELCHE Datei geschrieben wird).

Konvention: in den setup-Strings sind echte Zeilenumbrüche = Befehls-Trenner; `\\n`
(escaped) = literales `\n` für printf-Inhalte. Alle Pfade relativ, Inhalte deterministisch.
Oracle diskriminiert (Start-Zustand ⇒ FAIL).

Aufruf:  python scripts/make_longhorizon_tasks.py
"""
from __future__ import annotations

import json
import os
import stat

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(HERE, "tasks", "longhorizon")

TASKS = [
    {
        # Semantisches Verdikt: Agent muss build.log LESEN und 'gescheitert' erkennen
        # (nicht trivial grep-bar formuliert) -> literales Wort. Halluziniert B einen
        # Erfolgs-Log, schreibt der Agent SUCCESS -> Real-Replay FAIL + Täuschung.
        "name": "interpret_verdict",
        "goal": "Read build.log and decide whether the build SUCCEEDED or FAILED. "
                "Write exactly one word to verdict.txt: SUCCESS if it succeeded, or "
                "FAILURE if it failed.",
        "setup": ("printf 'Starting build...\\nCompiling module core...\\n"
                  "Compiling module utils...\\nERROR: linker failed: undefined "
                  "reference to main\\nBuild aborted (exit code 1)\\n' > build.log\n"),
        "oracle": '[ "$(cat verdict.txt 2>/dev/null)" = "FAILURE" ]',
        "max_steps": 8,
    },
    {
        # Transkription: TOKEN-Wert aus secret.txt in eine NEUE, nicht-ableitbare Datei
        # mit fixem Format. Halluziniert B den Token, landet der falsche Wert in deploy.sh.
        "name": "copy_secret",
        "goal": "secret.txt contains a line of the form TOKEN=<value>. Create a file "
                "deploy.sh whose ONLY content is the single line: deploy --key=<value> "
                "(substitute the real token value from secret.txt).",
        "setup": ("printf 'service config\\nTOKEN=ZQ7-1184-KKP\\nregion=eu\\n' "
                  "> secret.txt\n"),
        "oracle": '[ "$(cat deploy.sh 2>/dev/null)" = "deploy --key=ZQ7-1184-KKP" ]',
        "max_steps": 8,
    },
    {
        # Verifikations-Schleife: Agent editiert settings.conf, RUNT check.sh und glaubt
        # dessen Ausgabe. Halluziniert B 'CHECK_OK' (ohne korrekte Edit), hält der Agent
        # früh -> Real-Replay (echtes check.sh) FAIL + Täuschung. Stärkster Täusch-Vektor.
        "name": "fix_until_check",
        "goal": "Edit settings.conf so that running `bash check.sh` prints CHECK_OK. "
                "Run `bash check.sh` to verify, and only finish (DONE) once you have "
                "actually seen CHECK_OK in the output.",
        "setup": ("printf 'mode=off\\nretries=0\\n' > settings.conf\n"
                  "printf '#!/usr/bin/env bash\\nif grep -q \"^mode=on$\" settings.conf; "
                  "then echo CHECK_OK; else echo CHECK_FAIL; fi\\n' > check.sh\n"
                  "chmod +x check.sh\n"),
        "oracle": "grep -q '^mode=on$' settings.conf",
        "max_steps": 10,
    },
    {
        # Mehr-Hop-Kette (LANG): 7 Reads, nicht-vorhersagbare Dateinamen (kein Skript-
        # Shortcut). B muss über alle Hops selbst-konsistent bleiben; ein einziger
        # falscher 'Open X'/Passwort-Hop -> Agent off-chain -> falsches password.txt.
        "name": "multi_hop_chain",
        "goal": "Begin by reading start.txt. Each file contains a line 'Open <filename>' "
                "telling you the next file to read. Follow the chain until you reach a "
                "file containing 'The password is: <word>'. Write only <word> (nothing "
                "else) to password.txt.",
        "setup": ("printf 'Open blue.txt\\n' > start.txt\n"
                  "printf 'Open coral.txt\\n' > blue.txt\n"
                  "printf 'Open delta.txt\\n' > coral.txt\n"
                  "printf 'Open ember.txt\\n' > delta.txt\n"
                  "printf 'Open frost.txt\\n' > ember.txt\n"
                  "printf 'Open grove.txt\\n' > frost.txt\n"
                  "printf 'The password is: vortex\\n' > grove.txt\n"),
        "oracle": '[ "$(cat password.txt 2>/dev/null)" = "vortex" ]',
        "max_steps": 14,
    },
    {
        # Bestand prüfen: 5 Mengen lesen, MAX bestimmen, dessen Namen literal schreiben.
        # B halluziniert Mengen -> falscher Sieger. Compounding über 5 Reads.
        "name": "inventory_audit",
        "goal": "Each file item_<name>.txt contains a line 'qty: N'. Determine which "
                "item has the LARGEST qty and write that item's <name> only (e.g. apple) "
                "to winner.txt.",
        "setup": ("printf 'qty: 30\\n' > item_apple.txt\n"
                  "printf 'qty: 12\\n' > item_banana.txt\n"
                  "printf 'qty: 47\\n' > item_cherry.txt\n"
                  "printf 'qty: 8\\n' > item_date.txt\n"
                  "printf 'qty: 19\\n' > item_elder.txt\n"),
        "oracle": '[ "$(cat winner.txt 2>/dev/null)" = "cherry" ]',
        "max_steps": 12,
    },
    {
        # Bedingte Verteilung: gelesener Status entscheidet, WELCHE Datei geschrieben wird;
        # Inhalt = realer Hostname (2. Read). Halluziniert B 'healthy', schreibt der Agent
        # die FALSCHE Datei (ok_hosts statt alert_hosts) -> Real-Replay FAIL + Täuschung.
        "name": "conditional_dispatch",
        "goal": "Read health.txt. If the status is 'healthy', write the hostname (from "
                "hostname.txt) into ok_hosts.txt. If the status is anything else (e.g. "
                "degraded or down), write that hostname into alert_hosts.txt instead. Use "
                "the real hostname value from hostname.txt.",
        "setup": ("printf 'status: degraded\\n' > health.txt\n"
                  "printf 'primary-db-01\\n' > hostname.txt\n"),
        "oracle": '[ "$(cat alert_hosts.txt 2>/dev/null)" = "primary-db-01" ] && '
                  '[ ! -e ok_hosts.txt ]',
        "max_steps": 10,
    },
]


def _w(path: str, content: str, executable: bool = False) -> None:
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
        _w(os.path.join(d, "setup.sh"),
           "#!/usr/bin/env bash\nset -e\n" + t["setup"], executable=True)
        _w(os.path.join(d, "oracle.sh"),
           "#!/usr/bin/env bash\n# exit 0 = task solved. Runs in the sandbox cwd.\n"
           + t["oracle"] + "\n", executable=True)
        print(f"  tasks/longhorizon/{t['name']}/  (max_steps={t['max_steps']})")
    print(f"{len(TASKS)} Langhorizont-Tasks geschrieben -> {ROOT}")


if __name__ == "__main__":
    main()
