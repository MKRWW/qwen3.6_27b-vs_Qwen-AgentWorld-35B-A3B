#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
test -f backup/notes.txt && [ ! -e notes.txt ] && [ "$(cat backup/notes.txt)" = "remember the milk" ]
