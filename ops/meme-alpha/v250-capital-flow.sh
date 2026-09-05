#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
cd "$APP"
echo '=== MEME ALPHA v2.5.1 ADAPTIVE CAPITAL FLOW DEPLOY ==='

[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
node --input-type=module - <<'NODE'
import fs from 'node:fs';const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));if(c.mode!=='PAPER')throw new Error('ABORT_ANALYSIS_ENGINE_NOT_PAPER');console.log('ANALYSIS_MODE=PAPER');
NODE
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-signer.service
! systemctl is-active --quiet meme-alpha-micro-live.service

if test -r /var/lib/meme-alpha-signer/keys || test -x /var/lib/meme-alpha-signer/keys; then echo ABORT_RUNNER_KEY_ACCESS; exit 1; fi
if test -r /run/meme-alpha-signer/signer.sock || test -w /run/meme-alpha-signer/signer.sock; then echo ABORT_RUNNER_SIGNER_ACCESS; exit 1; fi

echo RUNNER_ISOLATION=PASS
B="code-backups/v251-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$B"
cp -a src/micro-live-executor.js "$B/micro-live-executor.js"

SRC="$REPO_ROOT/ops/meme-alpha/micro-live/micro-live-executor-v250.js"
SIGNERSRC="$REPO_ROOT/ops/meme-alpha/signer/ready_signer_v4.py"
ROOTSRC="$REPO_ROOT/ops/meme-alpha/v250-root-go-live.sh"
[ -f "$SRC" ] && [ -f "$SIGNERSRC" ] && [ -f "$ROOTSRC" ] || { echo ABORT_V251_BUNDLE_MISSING; exit 1; }

# Stage only non-secret code. The GitHub runner never creates/reads a wallet and cannot arm signing.
cat "$SRC" > src/micro-live-executor.js
mkdir -p ops/meme-alpha/signer
install -m 0644 "$SIGNERSRC" ops/meme-alpha/signer/ready_signer_v4.py
install -m 0755 "$ROOTSRC" ops/meme-alpha/v250-root-go-live.sh

node --check src/micro-live-executor.js
node src/micro-live-executor.js --self-test
python3 ops/meme-alpha/signer/ready_signer_v4.py --self-test

grep -q 'MICRO_LIVE_EXECUTOR_V250' src/micro-live-executor.js
grep -q 'ADAPTIVE_COMPOUND' src/micro-live-executor.js
grep -q 'CAPITAL_DEPOSIT_DETECTED' src/micro-live-executor.js
grep -q 'CAPITAL_WITHDRAWAL_DETECTED' src/micro-live-executor.js
grep -q 'READY_SIGNER_V4_SELF_TEST=PASS' <(python3 ops/meme-alpha/signer/ready_signer_v4.py --self-test)
grep -q 'SIGNER_DYNAMIC_BALANCE_LIMIT=TRUE' ops/meme-alpha/v250-root-go-live.sh
grep -q 'SIGNER_REQUIRES_FRESH_ELIGIBLE_SIGNAL_FOR_BUY=TRUE' ops/meme-alpha/v250-root-go-live.sh

# Staging must never turn on real execution.
! systemctl is-active --quiet meme-alpha-micro-live.service
if [ -e /etc/meme-alpha/execution-mode ]; then echo EXECUTION_MODE_FILE_PRESENT_PRE_ACTIVATION; else echo EXECUTION_MODE=DISABLED; fi

echo PRE_EVIDENCE_MAX_ENTRY_SOL=0.005
echo POST_EVIDENCE_BASE_UTILIZATION_PCT=70
echo POST_EVIDENCE_STRONG_UTILIZATION_PCT=82
echo POST_EVIDENCE_MAX_UTILIZATION_PCT=90
echo WITHDRAWAL_DEPOSIT_AWARE=TRUE
echo READY_SIGNER_V4_STAGED=TRUE
echo SIGNER_DYNAMIC_BALANCE_LIMIT=TRUE
echo SIGNER_REQUIRES_FRESH_ELIGIBLE_SIGNAL_FOR_BUY=TRUE
echo LIVE_EXECUTION=FALSE
echo NETWORK_EXECUTION_PERFORMED=FALSE
echo ROOT_ACTIVATION_SCRIPT=STAGED_V251
echo "BACKUP=$B"
echo V251_ADAPTIVE_CAPITAL_FLOW_DEPLOY_PASS
