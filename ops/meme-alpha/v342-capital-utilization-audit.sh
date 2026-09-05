#!/usr/bin/env bash
set -euo pipefail
F=/opt/meme-alpha/app/src/micro-live-executor.js
echo '=== V342 CAPITAL UTILIZATION AUDIT ==='
grep -nE "st\.version|allocationProfile\(|MICRO_LIVE_EXECUTOR|SELF_TEST|CONTINUOUS_ALLOCATION|EQUITY_GROWTH|CAPITAL_HEADROOM_LOW|TARGET_ALREADY_SATISFIED|portfolioInvested" "$F" | head -n 120
