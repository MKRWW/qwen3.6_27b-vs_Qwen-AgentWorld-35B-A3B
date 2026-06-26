#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat sorted_unique.txt 2>/dev/null)" = "$(printf 'alice\nbob\ncharlie')" ]
