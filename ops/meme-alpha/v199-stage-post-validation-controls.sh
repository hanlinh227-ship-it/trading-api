#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DST=$APP/ops/security
SRC="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_RUNNER; exit 1; }
mkdir -p "$DST"
stage(){ local src="$1" out="$2" mode="$3"; local t="$DST/$out.new-$$"; cat "$src" > "$t"; chmod "$mode" "$t"; mv -f "$t" "$DST/$out"; }
stage "$SRC/signer/ready_signer_v3.py" ready_signer.py 0755
stage "$SRC/v170-root-install-ready-signer.sh" v170-root-install-ready-signer.sh 0750
stage "$SRC/v180-root-create-wallet-after-validation.sh" v180-root-create-wallet-after-validation.sh 0750
stage "$SRC/v181-root-arm-micro-live.sh" v181-root-arm-micro-live.sh 0750
stage "$SRC/v191-root-install-micro-executor.sh" v191-root-install-micro-executor.sh 0750
stage "$SRC/v192-root-emergency-disarm.sh" v192-root-emergency-disarm.sh 0750
stage "$SRC/micro-live/micro-live-executor.js" micro-live-executor.js 0644
python3 -m py_compile "$DST/ready_signer.py"
python3 "$DST/ready_signer.py" --self-test
for f in v170-root-install-ready-signer.sh v180-root-create-wallet-after-validation.sh v181-root-arm-micro-live.sh v191-root-install-micro-executor.sh v192-root-emergency-disarm.sh; do bash -n "$DST/$f"; done
node --check "$DST/micro-live-executor.js"
node "$DST/micro-live-executor.js" --self-test
if [ -r /var/lib/meme-alpha-signer/keys ] || [ -x /var/lib/meme-alpha-signer/keys ]; then echo FAIL_RUNNER_KEY_ACCESS; exit 1; fi
[ ! -e /etc/meme-alpha/execution-mode ] || { echo FAIL_EXECUTION_MODE_ALREADY_ARMED; exit 1; }
echo READY_SIGNER_V3=STAGED_PASS
echo WALLET_CREATOR=STAGED_GATED
echo MICRO_EXECUTOR=STAGED_DISABLED
echo ARM_CONTROL=STAGED_GATED
echo EMERGENCY_DISARM=STAGED_PASS
echo RUNNER_KEY_ACCESS=DENIED_PASS
echo LIVE_EXECUTION=FALSE
echo V199_POST_VALIDATION_CONTROLS_PASS
