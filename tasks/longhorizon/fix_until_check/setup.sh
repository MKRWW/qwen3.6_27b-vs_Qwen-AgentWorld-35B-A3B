#!/usr/bin/env bash
set -e
printf 'mode=off\nretries=0\n' > settings.conf
printf '#!/usr/bin/env bash\nif grep -q "^mode=on$" settings.conf; then echo CHECK_OK; else echo CHECK_FAIL; fi\n' > check.sh
chmod +x check.sh
