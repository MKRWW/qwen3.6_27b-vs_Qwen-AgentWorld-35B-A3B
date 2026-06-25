#!/usr/bin/env bash
# Oracle: Tests muessen gruen sein. exit 0 == Task geloest.
# Working Dir == Sandbox (von run_track1_policy.py gesetzt), Tests liegen hier.
set -e
python3 -m pytest -q test_utils.py
