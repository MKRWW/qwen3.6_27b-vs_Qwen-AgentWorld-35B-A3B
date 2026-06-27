#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
test -f new.txt && [ ! -e old.txt ] && [ "$(cat new.txt)" = "payload-content" ]
