#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
EXE="$APP/src/micro-live-executor.js"
echo '=== V360 PREUPGRADE AUDIT ==='
echo "HOST=$(hostname -f 2>/dev/null || hostname)"
echo "EXECUTOR_SHA=$(sha256sum "$EXE" | awk '{print $1}')"
grep -n "async function manageOnePosition\|function profitPlan\|function softTrendWeak\|function severeTrendBreak\|function rotationSource\|async function maybeRotate\|async function sellFraction\|async function sell(" "$EXE" || true
for p in /usr/local/sbin/meme-alpha-deploy /usr/local/sbin/meme-alpha-safe-deploy /usr/local/sbin/meme-alpha-deploy-dispatcher /opt/meme-alpha/app/runtime-status/v357-bootstrap/install-safe-autodeploy.sh; do
  if [ -e "$p" ]; then stat -c "PATH=%n owner=%U group=%G mode=%a" "$p"; else echo "PATH_MISSING=$p"; fi
done
echo '--- sudo noninteractive list ---'
sudo -n -l 2>&1 || true
echo '--- services ---'
for s in meme-alpha-micro-live.service meme-alpha-paper.service meme-alpha-realtime-pulse.service meme-alpha-whale-flow.service meme-alpha-signer.service; do printf '%s=' "$s"; systemctl is-active "$s" 2>/dev/null || true; done
echo V360_PREUPGRADE_AUDIT=COMPLETE
