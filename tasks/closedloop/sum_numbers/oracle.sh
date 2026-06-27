#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat sum.txt 2>/dev/null)" = "25" ]
