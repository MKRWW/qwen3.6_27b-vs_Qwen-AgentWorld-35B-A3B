#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat verdict.txt 2>/dev/null)" = "FAILURE" ]
