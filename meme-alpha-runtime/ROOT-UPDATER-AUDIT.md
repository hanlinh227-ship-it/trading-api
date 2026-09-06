# Root Updater Audit

- updater_exists: `True`
- updater_readable: `True`

## Sanitized updater source
```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/github_watch.log"
LOCK="/tmp/auto-futures-update.lock"
BRANCH="auto-futures-v1"
BOT="$ROOT/auto-futures-v1"

mkdir -p "$(dirname "$LOG")"
log(){ echo "$(date -u -Is) $*" >> "$LOG"; }

cd "$ROOT"
exec 9>"$LOCK"
if ! flock -n 9; then log "SKIP: another update is running"; exit 0; fi

git fetch origin "$BRANCH" >/dev/null 2>&1
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL" != "$REMOTE" ]]; then
  log "NEW COMMIT: local=$LOCAL remote=$REMOTE"
  log "STARTING SAFE UPDATE"
  "$BOT/runtime/update_auto_futures.sh" >> "$LOG" 2>&1
  log "UPDATE FINISHED"
  exit 0
fi

# Self-heal the one-Hub architecture after an older updater has pulled the new release.
NEEDS_RECONCILE=0
systemctl cat auto-futures-hub-bridge.service >/dev/null 2>&1 || NEEDS_RECONCILE=1
if systemctl is-active --quiet auto-futures-telegram.service 2>/dev/null; then NEEDS_RECONCILE=1; fi
if [[ "$NEEDS_RECONCILE" -eq 1 ]]; then
  log "NO GIT UPDATE, BUT UNIFIED HUB RECONCILE REQUIRED"
  "$BOT/runtime/unified_bootstrap.sh" >> "$LOG" 2>&1
  log "UNIFIED HUB RECONCILE FINISHED"
else
  log "NO UPDATE: $LOCAL | UNIFIED HUB HEALTHY"
fi
```

- updater_repo_origin: `UNKNOWN`
