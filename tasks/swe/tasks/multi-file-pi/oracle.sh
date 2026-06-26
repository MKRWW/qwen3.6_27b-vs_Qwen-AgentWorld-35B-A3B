#!/usr/bin/env bash
# Oracle: alle Tests gruen. Working Dir == Sandbox.
set -e
python3 -m pytest -q test_geometry.py
