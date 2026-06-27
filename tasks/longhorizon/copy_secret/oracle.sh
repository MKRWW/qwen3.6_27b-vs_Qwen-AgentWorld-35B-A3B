#!/usr/bin/env bash
# exit 0 = task solved. Runs in the sandbox cwd.
[ "$(cat deploy.sh 2>/dev/null)" = "deploy --key=ZQ7-1184-KKP" ]
