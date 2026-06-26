#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat apples.txt 2>/dev/null)" = "$(printf 'apple pie\ngreen apple\napple')" ]
