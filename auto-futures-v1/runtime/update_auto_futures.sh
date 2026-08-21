#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/opt/trading/trading-api"
BOT="$ROOT/auto-futures-v1"

BACKUP_ROOT="/opt/trading/auto-futures-backups"
LOG="$BOT/logs/auto_update.log"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$BACKUP_ROOT/release_$TIMESTAMP"

UPDATE_STARTED=0
BACKUP_READY=0


log() {
    echo "$(date -u -Is) $*" | tee -a "$LOG"
}


rollback() {

    rc=$?

    trap - ERR

    log "UPDATE FAILED rc=$rc"

    if [[ "$BACKUP_READY" -eq 1 ]] \
       && [[ -d "$BACKUP/auto-futures-v1" ]]; then

        log "ROLLBACK START"

        systemctl stop auto-futures-position.service 2>/dev/null || true
        systemctl stop auto-futures-scan.timer 2>/dev/null || true

        FAILED="$ROOT/auto-futures-v1.failed.$TIMESTAMP"

        if [[ -d "$BOT" ]]; then
            mv "$BOT" "$FAILED"
        fi

        cp -a \
            "$BACKUP/auto-futures-v1" \
            "$BOT"

        systemctl daemon-reload || true

        systemctl restart \
            auto-futures-position.service \
            2>/dev/null || true

        systemctl restart \
            auto-futures-scan.timer \
            2>/dev/null || true

        log "ROLLBACK COMPLETE"

    else

        log "ROLLBACK SKIPPED: no valid backup"

    fi

    exit "$rc"
}


trap rollback ERR


mkdir -p "$BACKUP_ROOT"
mkdir -p "$BOT/logs"

cd "$ROOT"

log "========================================"
log "AUTO FUTURES UPDATE START"
log "========================================"


# ============================================================
# 1. BACKUP OUTSIDE BOT DIRECTORY
# ============================================================

mkdir -p "$BACKUP"

cp -a \
    "$BOT" \
    "$BACKUP/auto-futures-v1"

BACKUP_READY=1

log "BACKUP PASS: $BACKUP"


# ============================================================
# 2. HARD LOCK LIVE TRADING
# ============================================================

if [[ -f /opt/trading/.env.binance ]]; then

    if grep -q '^BINANCE_LIVE_TRADING=' \
        /opt/trading/.env.binance; then

        sed -i \
        's/^BINANCE_LIVE_TRADING=.*/BINANCE_LIVE_TRADING="false"/' \
        /opt/trading/.env.binance

    else

        echo 'BINANCE_LIVE_TRADING="false"' \
        >> /opt/trading/.env.binance

    fi


    if grep -q '^BINANCE_LIVE_ARMED=' \
        /opt/trading/.env.binance; then

        sed -i \
        's/^BINANCE_LIVE_ARMED=.*/BINANCE_LIVE_ARMED="false"/' \
        /opt/trading/.env.binance

    else

        echo 'BINANCE_LIVE_ARMED="false"' \
        >> /opt/trading/.env.binance

    fi

    chmod 600 /opt/trading/.env.binance

fi

log "LIVE SAFETY LOCK PASS"


# ============================================================
# 3. CHECK GIT STATE
# ============================================================

git fetch origin

CURRENT_BRANCH="$(git branch --show-current)"

log "CURRENT BRANCH: $CURRENT_BRANCH"

if [[ "$CURRENT_BRANCH" != "main" ]]; then
    git checkout main
fi


# Do not destroy local work automatically.
if [[ -n "$(git status --porcelain)" ]]; then

    log "WARNING: repository contains local changes"

    git status --short | tee -a "$LOG"

fi


# ============================================================
# 4. UPDATE MAIN
# ============================================================

git pull --ff-only origin main

UPDATE_STARTED=1

log "GITHUB UPDATE PASS"


# ============================================================
# 5. LOAD ENVIRONMENT
# ============================================================

if [[ -f /opt/trading/.env.ai ]]; then

    set -a
    source /opt/trading/.env.ai
    set +a

fi


if [[ -f /opt/trading/.env.binance ]]; then

    set -a
    source /opt/trading/.env.binance
    set +a

fi


# ============================================================
# 6. HARD SAFETY FLAGS
# ============================================================

if [[ "${BINANCE_LIVE_TRADING:-false}" != "false" ]]; then
    log "FAIL: BINANCE_LIVE_TRADING != false"
    exit 20
fi

if [[ "${BINANCE_LIVE_ARMED:-false}" != "false" ]]; then
    log "FAIL: BINANCE_LIVE_ARMED != false"
    exit 21
fi

log "SAFETY FLAGS PASS"


# ============================================================
# 7. PYTHON SYNTAX
# ============================================================

FILES=(
    auto-futures-v1/paper_trader.py
    auto-futures-v1/ai/common.py
    auto-futures-v1/ai/claude_trader.py
    auto-futures-v1/ai/deepseek_trader.py
    auto-futures-v1/ai/codex_trader.py
    auto-futures-v1/ai/consensus.py
    auto-futures-v1/risk/risk_engine.py
    auto-futures-v1/execution/execution_guard.py
    auto-futures-v1/execution/emergency_stop.py
    auto-futures-v1/execution/binance_executor.py
    auto-futures-v1/execution/live_executor.py
    auto-futures-v1/position/position_manager.py
)

for f in "${FILES[@]}"; do

    if [[ ! -f "$ROOT/$f" ]]; then
        log "FAIL: missing $f"
        exit 30
    fi

done


python3 -m py_compile "${FILES[@]}"

log "PYTHON SYNTAX PASS"


# ============================================================
# 8. CLAUDE TEST
# ============================================================

timeout 120 \
claude \
--model sonnet \
-p 'Return exactly this JSON and nothing else: {"status":"OK"}' \
> /tmp/auto_futures_claude.out \
2> /tmp/auto_futures_claude.err


grep -Eq \
'"status"[[:space:]]*:[[:space:]]*"OK"' \
/tmp/auto_futures_claude.out

log "CLAUDE PASS"


# ============================================================
# 9. DEEPSEEK TEST
# ============================================================

python3 \
auto-futures-v1/ai/deepseek_trader.py \
> /tmp/auto_futures_deepseek.out


grep -Eq \
'"status"[[:space:]]*:[[:space:]]*"OK"' \
/tmp/auto_futures_deepseek.out

log "DEEPSEEK PASS"


# ============================================================
# 10. CODEX TEST
# ============================================================

timeout 180 \
codex exec \
'Return exactly this JSON and nothing else: {"status":"OK"}' \
> /tmp/auto_futures_codex.out \
2> /tmp/auto_futures_codex.err


grep -Eq \
'"status"[[:space:]]*:[[:space:]]*"OK"' \
/tmp/auto_futures_codex.out

log "CODEX PASS"


# ============================================================
# 11. EMERGENCY STOP OFF FOR PAPER
# ============================================================

python3 \
auto-futures-v1/execution/emergency_stop.py \
off \
> /tmp/auto_futures_emergency.out

log "PAPER EMERGENCY STATE PASS"


# ============================================================
# 12. FULL PAPER PIPELINE
# ============================================================

timeout 700 \
"$BOT/run_pipeline.sh" \
> /tmp/auto_futures_pipeline.out \
2>&1


grep -q \
"PIPELINE COMPLETE" \
/tmp/auto_futures_pipeline.out


grep -q \
"NO REAL BINANCE ORDER WAS SENT" \
/tmp/auto_futures_pipeline.out

log "PAPER PIPELINE PASS"


# ============================================================
# 13. EXECUTION GUARD TEST
# ============================================================

python3 \
auto-futures-v1/execution/execution_guard.py \
> /tmp/auto_futures_guard.out

grep -q \
"NO BINANCE ORDER AUTHORITY" \
/tmp/auto_futures_guard.out

log "EXECUTION GUARD PASS"


# ============================================================
# 14. LIVE EXECUTOR LOCK TEST
# ============================================================

python3 \
auto-futures-v1/execution/live_executor.py \
> /tmp/auto_futures_live_executor.out


grep -q \
"NO REAL ORDER WAS SENT" \
/tmp/auto_futures_live_executor.out

grep -q \
"LIVE EXECUTION LOCKED" \
/tmp/auto_futures_live_executor.out

log "LIVE EXECUTOR LOCK PASS"


# ============================================================
# 15. SERVICES
# ============================================================

systemctl daemon-reload

systemctl enable \
    auto-futures-position.service \
    >/dev/null

systemctl enable \
    auto-futures-scan.timer \
    >/dev/null

systemctl restart \
    auto-futures-position.service

systemctl restart \
    auto-futures-scan.timer

log "SERVICES RESTARTED"


# ============================================================
# 16. HEALTH CHECK
# ============================================================

sleep 3

POSITION="$(
    systemctl is-active \
    auto-futures-position.service
)"

TIMER="$(
    systemctl is-active \
    auto-futures-scan.timer
)"


if [[ "$POSITION" != "active" ]]; then

    log "FAIL: position service=$POSITION"
    exit 40

fi


if [[ "$TIMER" != "active" ]]; then

    log "FAIL: scan timer=$TIMER"
    exit 41

fi


log "POSITION SERVICE: $POSITION"
log "SCAN TIMER: $TIMER"
log "HEALTH CHECK PASS"


# ============================================================
# 17. RETENTION
# Keep latest backup history without recursive backup problem.
# ============================================================

find "$BACKUP_ROOT" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
    -name 'release_*' \
    -mtime +14 \
    -exec rm -rf {} + \
    2>/dev/null || true


log "========================================"
log "AUTO UPDATE COMPLETE"
log "PAPER SAFE"
log "LIVE_TRADING=false"
log "LIVE_ARMED=false"
log "========================================"

trap - ERR

exit 0
