#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
test -f greeting.txt && [ "$(cat greeting.txt)" = "hello world" ]
