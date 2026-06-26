#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(sed -n 1p log.txt)" = "alpha" ] && [ "$(sed -n 2p log.txt)" = "beta" ] && [ "$(sed -n 3p log.txt)" = "DONE" ] && [ "$(wc -l < log.txt)" -eq 3 ]
