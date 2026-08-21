#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
LOG="$ROOT/auto-futures-v1/logs/github_watch.log"
LOCK="/tmp/auto-futures-update.lock"
BRANCH="auto-futures-v1"

mkdir -p "$(dirname "$LOG")"

log() {
    echo "$(date -u -Is) $*" >> "$LOG"
}

cd "$ROOT"
exec 9>"$LOCK"

if ! flock -n 9; then
    log "SKIP: another update is running"
    exit 0
fi

git fetch origin "$BRANCH" >/dev/null 2>&1

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL" == "$REMOTE" ]]; then
    log "NO UPDATE: $LOCAL"
    exit 0
fi

log "NEW COMMIT: local=$LOCAL remote=$REMOTE"
log "STARTING SAFE UPDATE"

/usr/local/bin/update-futures >> "$LOG" 2>&1

log "UPDATE FINISHED"
