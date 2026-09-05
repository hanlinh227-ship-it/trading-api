#!/usr/bin/env bash
set -euo pipefail

APP=/opt/meme-alpha/app
DST=$APP/ops/security
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -un)" = github-runner ] || { echo "ABORT_EXPECTED_GITHUB_RUNNER got=$(id -un)"; exit 1; }
python3 - <<'PY'
import json
with open('/opt/meme-alpha/app/config/runtime.json','r',encoding='utf-8') as f: c=json.load(f)
if c.get('mode') != 'PAPER': raise SystemExit('ABORT_NOT_PAPER')
print('MODE=PAPER')
print('LIVE_EXECUTION=DISABLED')
PY

mkdir -p "$DST"
install -m 0755 "$SRC_DIR/signer/locked_signer.py" "$DST/locked_signer.py"
install -m 0750 "$SRC_DIR/v142-root-install-signer-isolation.sh" "$DST/v142-root-install-signer-isolation.sh"

python3 -m py_compile "$DST/locked_signer.py"
bash -n "$DST/v142-root-install-signer-isolation.sh"

# Runner must remain unable to access current wallet directory.
if [ -r /var/lib/meme-alpha/wallet ] || [ -x /var/lib/meme-alpha/wallet ]; then
  echo 'FAIL_RUNNER_CAN_ACCESS_EXISTING_WALLET_DIR'
  exit 1
fi

echo "STAGED_LOCKED_SIGNER=$DST/locked_signer.py"
echo "STAGED_ROOT_INSTALLER=$DST/v142-root-install-signer-isolation.sh"
echo 'RUNNER_WALLET_ACCESS=DENIED_PASS'
echo 'NO_WALLET_CREATED=TRUE'
echo 'NO_LIVE_ENABLE=TRUE'
echo 'V142_STAGE_PASS'
