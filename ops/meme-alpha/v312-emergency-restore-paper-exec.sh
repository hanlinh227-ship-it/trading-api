#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RUN="$APP/run-paper.sh"
SERVICE=meme-alpha-paper.service
[ -r "$RUN" ] || { echo RUN_PAPER_MISSING; exit 2; }
[ -w "$APP" ] || { echo APP_DIR_NOT_WRITABLE; exit 3; }
# Preserve the already-rolled-back safe content, restore executable mode atomically.
tmp="$APP/.run-paper-exec-restore.$$.sh"
cp "$RUN" "$tmp"
/bin/bash -n "$tmp"
chmod 775 "$tmp"
mv -f "$tmp" "$RUN"
stat -c 'RUN_PAPER owner=%U group=%G mode=%a size=%s' "$RUN"
sudo -n /bin/systemctl restart "$SERVICE"
sleep 2
sudo -n /bin/systemctl is-active "$SERVICE"
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=6' "$RUN"
echo V312_EMERGENCY_PAPER_RESTORE_PASS
