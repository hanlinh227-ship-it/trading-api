#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V377_DEPLOY=DEFER_NOT_ROOT'; exit 0; }
APP=/opt/meme-alpha/app
EXECUTOR="$APP/src/micro-live-executor.js"
[[ -f "$EXECUTOR" ]] || { echo 'MEME_V377_DEPLOY=DEFER_MISSING_EXECUTOR'; exit 0; }
# v3.79+ fully supersedes this legacy deploy lane. Never patch a newer
# executor backwards. v3.77 remains retired and fail-closed for unknown builds.
if grep -Eq 'MICRO_LIVE_EXECUTOR_V38[0-9]|MICRO_LIVE_EXECUTOR_V379_HIGH_OPPORTUNITY|MICRO_LIVE_EXECUTOR_V378_AGGRESSIVE_ROTATION' "$EXECUTOR"; then
  echo 'MEME_V377_DEPLOY=ALREADY_SUPERSEDED'
  exit 0
fi
echo 'MEME_V377_DEPLOY=DEFER_LEGACY_RETIRED'
exit 0
