# Tasks — Schemata

Zwei Aufgabentypen, beide unter `tasks/<domain>/` (`domain` ∈ {terminal, swe}).

## Track 1 — Policy-Tasks  (`tasks/<domain>/tasks/<name>/`)

```
tasks/swe/tasks/fix-off-by-one/
├── task.json        # { "domain","prompt","_meta" }
├── workspace/       # Start-Zustand; wird je Run in frische Sandbox kopiert
└── oracle.sh        # exit 0 == success (z. B. `pytest -q`)
```

`task.json`:
```json
{
  "domain": "swe",
  "prompt": "In utils.py liefert sum_range() ein um 1 zu kleines Ergebnis. Finde und behebe den Bug. Die Tests in test_utils.py müssen grün sein.",
  "_meta": { "author": "markus", "created": "2026-06-25", "difficulty": "easy" }
}
```

**Oracle-Vertrag:** `oracle.sh` läuft im Sandbox-Verzeichnis (Working Dir =
modifizierter Workspace), exit-Code 0 = Task gelöst. Determiniert, kein Netz.

## Track 2 — World-Model-Triples  (`tasks/<domain>/triples/<name>.json`)

Per `scripts/gen_triples.py` aus echten WSL-Sandbox-Läufen erzeugt (Ground truth).

```json
{
  "domain": "terminal",
  "history": [
    { "action": "mkdir demo && cd demo", "observation": "" },
    { "action": "echo hello > a.txt", "observation": "" }
  ],
  "action": "cat a.txt && ls -1 && echo $?",
  "truth": {
    "stdout": "hello\na.txt\n0",
    "stderr": "",
    "exit_code": 0,
    "fs_delta": ["a.txt"]
  },
  "format_schema": null
}
```

**Wichtig (Anti-Kontamination & Fairness):**
- `truth` wird **immer real ausgeführt**, nie von Hand geraten.
- Triples werden **vor** den Modell-Läufen committet (Git-Zeitstempel).
- Keine Triples nach Sichtung der Ergebnisse entfernen (siehe THREATS §9).
