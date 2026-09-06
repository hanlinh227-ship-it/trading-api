#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V378_DEPLOY=DEFER_NOT_ROOT'; exit 0; }
APP=/opt/meme-alpha/app
EXECUTOR="$APP/src/micro-live-executor.js"
PATCHER=/opt/trading/trading-api/auto-futures-v1/runtime/meme_alpha_patch_v378.py
BACKUP_ROOT=/opt/meme-alpha/backups
LOCK=/tmp/meme-alpha-v378-deploy.lock
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v378_$TS"
TMP="$(mktemp -d /tmp/meme-alpha-v378.XXXXXX)"
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT
exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V378_DEPLOY=DEFER_LOCK_BUSY'; exit 0; fi
for f in "$EXECUTOR" "$PATCHER"; do [[ -f "$f" ]] || { echo "MEME_V378_DEPLOY=DEFER_MISSING_FILE name=$(basename "$f")"; exit 0; }; done
if grep -q 'MICRO_LIVE_EXECUTOR_V378_AGGRESSIVE_ROTATION' "$EXECUTOR"; then echo 'MEME_V378_DEPLOY=ALREADY_APPLIED'; exit 0; fi
cp -a "$EXECUTOR" "$TMP/micro-live-executor.js"
python3 "$PATCHER" "$TMP/micro-live-executor.js"
node --check "$TMP/micro-live-executor.js"
node "$TMP/micro-live-executor.js" --self-test >/tmp/meme_v378_selftest.out 2>&1
grep -q 'MICRO_LIVE_EXECUTOR_V378_AGGRESSIVE_ROTATION' "$TMP/micro-live-executor.js"
mkdir -p "$BACKUP"
cp -a "$EXECUTOR" "$BACKUP/micro-live-executor.js"
rollback(){ rc=$?; trap - ERR; cp -a "$BACKUP/micro-live-executor.js" "$EXECUTOR" 2>/dev/null || true; systemctl restart meme-alpha-micro-live.service 2>/dev/null || true; echo "MEME_V378_DEPLOY=ROLLBACK rc=$rc"; exit "$rc"; }
trap rollback ERR
systemctl stop meme-alpha-micro-live.service
owner="$(stat -c %U "$EXECUTOR")"; group="$(stat -c %G "$EXECUTOR")"; mode="$(stat -c %a "$EXECUTOR")"
install -o "$owner" -g "$group" -m "$mode" "$TMP/micro-live-executor.js" "$EXECUTOR"
node --check "$EXECUTOR"
systemctl start meme-alpha-micro-live.service
sleep 3
systemctl is-active --quiet meme-alpha-micro-live.service
mkdir -p "$APP/runtime-status"
printf '{"version":"3.78.0","status":"DEPLOYED","profile":"AGGRESSIVE_ROTATION","timestamp":"%s"}\n' "$(date -u +%FT%TZ)" > "$APP/runtime-status/v378-deployed.json"
chmod 0664 "$APP/runtime-status/v378-deployed.json" || true
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'v378_*' -mtime +14 -exec rm -rf {} + 2>/dev/null || true
trap - ERR
echo 'MEME_V378_DEPLOY=SUCCESS'
