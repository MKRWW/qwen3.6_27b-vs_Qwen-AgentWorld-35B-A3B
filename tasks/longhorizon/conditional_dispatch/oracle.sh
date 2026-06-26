#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat alert_hosts.txt 2>/dev/null)" = "primary-db-01" ] && [ ! -e ok_hosts.txt ]
