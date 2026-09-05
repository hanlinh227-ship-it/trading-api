#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
systemctl is-active --quiet meme-alpha-micro-live.service
if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo '=== MEME ALPHA v2.7.0 FULL-CAPITAL AUTOSCALE STAGE ==='
node --check "$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v270.js"
node "$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v270.js" --self-test
python3 "$ROOT/ops/meme-alpha/signer/ready_signer_v5.py" --self-test

mkdir -p "$APP/ops/meme-alpha/micro-live" "$APP/ops/meme-alpha/signer"
install -m 0644 "$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v270.js" "$APP/ops/meme-alpha/micro-live/micro-live-executor-v270.js"
install -m 0644 "$ROOT/ops/meme-alpha/signer/ready_signer_v5.py" "$APP/ops/meme-alpha/signer/ready_signer_v5.py"
install -m 0755 "$ROOT/ops/meme-alpha/v270-root-apply-full-capital.sh" "$APP/ops/meme-alpha/v270-root-apply-full-capital.sh"

node --check "$APP/ops/meme-alpha/micro-live/micro-live-executor-v270.js"
python3 "$APP/ops/meme-alpha/signer/ready_signer_v5.py" --self-test | grep -q 'READY_SIGNER_V5_SELF_TEST=PASS'
grep -q 'V270_FULL_CAPITAL_AUTOSCALE_APPLY_PASS' "$APP/ops/meme-alpha/v270-root-apply-full-capital.sh"

echo RUNNER_ISOLATION=PASS
echo LIVE_RUNTIME_CHANGED=FALSE
echo ROOT_APPLY_REQUIRED=TRUE
echo STAGED_EXECUTOR_V270=TRUE
echo STAGED_SIGNER_V5=TRUE
echo STAGED_ROOT_APPLY=TRUE
echo TARGET_UTILIZATION_STAGES=15_35_65_94
echo MAX_UTILIZATION_PCT=94
echo RESERVE_SOL=0.010
echo V270_STAGE_PASS
