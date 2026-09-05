#!/usr/bin/env bash
set -euo pipefail

echo '=== MEME ALPHA v1.4.1 RUNNER ISOLATION VERIFY ==='
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
APP=/opt/meme-alpha/app

uid=$(id -u); user=$(id -un); groups=$(id -Gn)
echo "VERIFY_UID=$uid"
echo "VERIFY_USER=$user"
echo "VERIFY_GROUPS=$groups"
[ "$user" = 'github-runner' ] || { echo 'FAIL_RUNNER_NOT_GITHUB_RUNNER'; exit 1; }
[ "$uid" -ne 0 ] || { echo 'FAIL_RUNNER_STILL_ROOT'; exit 1; }

eff=$(systemctl show "$RUNNER_UNIT" -p User --value)
echo "SYSTEMD_RUNNER_USER=$eff"
[ "$eff" = 'github-runner' ] || { echo 'FAIL_SYSTEMD_RUNNER_USER'; exit 1; }

systemctl is-active --quiet "$RUNNER_UNIT"
systemctl is-active --quiet meme-alpha-paper.service
echo 'SERVICES_ACTIVE=PASS'

# Runner needs to deploy app code, but not read the wallet directory.
testfile="$APP/.runner-write-test-$$"
printf 'ok\n' > "$testfile"
rm -f "$testfile"
echo 'APP_DEPLOY_WRITE=PASS'

if [ -r /var/lib/meme-alpha/wallet ] || [ -x /var/lib/meme-alpha/wallet ]; then
  echo 'FAIL_RUNNER_CAN_ACCESS_WALLET_DIR'
  exit 1
else
  echo 'RUNNER_WALLET_ACCESS=DENIED_PASS'
fi

# Narrow sudo must work only for paper service status/restart commands.
sudo -n /bin/systemctl is-active meme-alpha-paper.service >/dev/null
echo 'NARROW_SUDO_PAPER_STATUS=PASS'
if sudo -n /usr/bin/id >/dev/null 2>&1; then
  echo 'FAIL_ARBITRARY_SUDO_AVAILABLE'
  exit 1
else
  echo 'ARBITRARY_SUDO=DENIED_PASS'
fi

# Bot itself remains paper-only.
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('/opt/meme-alpha/app/config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('FAIL_NOT_PAPER');
console.log('MODE=PAPER');
console.log('LIVE_EXECUTION=DISABLED');
NODE

echo 'V141_RUNNER_ISOLATION_PASS'
