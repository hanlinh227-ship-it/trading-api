#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUNNER_UNIT=actions.runner.hanlinh227-ship-it-trading-api.trading-vps.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
[ "$(id -un)" = github-runner ] || { echo ABORT_NOT_GITHUB_RUNNER; exit 1; }
[ "$(systemctl show "$RUNNER_UNIT" -p User --value)" = github-runner ] || { echo ABORT_RUNNER_ISOLATION; exit 1; }
systemctl is-active --quiet meme-alpha-paper.service
systemctl is-active --quiet meme-alpha-trend-pulse.service
systemctl is-active --quiet meme-alpha-micro-live.service
SRC="$ROOT/ops/meme-alpha/portfolio-shadow-v220.js"
DST="$APP/ops/meme-alpha/portfolio-shadow-v220.js"
cp "$SRC" "$DST"
node --check "$DST"
node "$DST" --self-test | tee /tmp/v220-shadow.txt
grep -q 'PORTFOLIO_SHADOW_V220_SELF_TEST=PASS' /tmp/v220-shadow.txt
cat /tmp/v220-shadow.txt
rm -f /tmp/v220-shadow.txt
echo LIVE_RUNTIME_CHANGED=FALSE
echo MAX_POSITIONS_SHADOW=3
echo MAX_SINGLE_POSITION_PCT=32
echo MAX_NARRATIVE_PCT=45
echo MAX_PORTFOLIO_PCT=94
echo RESERVE_SOL=0.01
echo V220_PORTFOLIO_SHADOW_STAGE_PASS
