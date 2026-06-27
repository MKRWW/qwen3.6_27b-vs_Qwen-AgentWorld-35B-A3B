#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat count.txt 2>/dev/null)" = "5" ]
