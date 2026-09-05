#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
DATA=/var/lib/meme-alpha/data/paper
LOG=/var/log/meme-alpha/paper.log
ERR=/var/log/meme-alpha/paper-error.log
SERVICE=meme-alpha-paper.service
cd "$APP"

echo '=== MEME ALPHA v1.3.2 RUNTIME PERMISSION HARDENING ==='
node --input-type=module - <<'NODE'
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
if(c.mode!=='PAPER') throw new Error('ABORT_NOT_PAPER');
console.log('MODE=PAPER');
NODE

SVC_USER=$(systemctl show "$SERVICE" -p User --value)
SVC_GROUP=$(systemctl show "$SERVICE" -p Group --value)
[ -n "$SVC_USER" ] || { echo 'SERVICE_USER_EMPTY'; exit 1; }
if [ -z "$SVC_GROUP" ]; then SVC_GROUP=$(id -gn "$SVC_USER"); fi
echo "SERVICE_USER=$SVC_USER"
echo "SERVICE_GROUP=$SVC_GROUP"

B=/var/lib/meme-alpha/data/backups/v132-permissions-$(date -u +%Y%m%d-%H%M%S)
mkdir -p "$B"
cp -a "$DATA" "$B/paper-data" 2>/dev/null || true

# Runtime state belongs to the unprivileged bot service, never world-writable.
chown -R "$SVC_USER:$SVC_GROUP" "$DATA"
find "$DATA" -type d -exec chmod 750 {} +
find "$DATA" -type f -exec chmod 640 {} +

# Explicitly verify files that root-run deploys may have created.
for f in reaction-history.jsonl reaction-telemetry.json entry-exit-intelligence.json stress-validation.json; do
  if [ -e "$DATA/$f" ]; then
    runuser -u "$SVC_USER" -- test -r "$DATA/$f"
    runuser -u "$SVC_USER" -- test -w "$DATA/$f"
    echo "SERVICE_RW_PASS=$f"
  fi
done
runuser -u "$SVC_USER" -- test -w "$DATA"
echo 'SERVICE_DATA_DIR_WRITE=PASS'

# Re-run the failing module as the actual systemd user.
runuser -u "$SVC_USER" -- /usr/bin/node src/reaction-telemetry.js | tail -20
runuser -u "$SVC_USER" -- /usr/bin/node src/stress-validation.js | tail -20

echo '=== RESTART SERVICE ==='
systemctl restart "$SERVICE"
sleep 3
systemctl is-active "$SERVICE"
systemctl is-enabled "$SERVICE"

START_OUT=$(wc -l < "$LOG")
START_ERR=$(wc -l < "$ERR")
echo "SOAK_START_OUT=$START_OUT SOAK_START_ERR=$START_ERR"
sleep 100
END_OUT=$(wc -l < "$LOG")
END_ERR=$(wc -l < "$ERR")
OUTTMP=$(mktemp)
ERRTMP=$(mktemp)
sed -n "$((START_OUT+1)),${END_OUT}p" "$LOG" > "$OUTTMP"
sed -n "$((START_ERR+1)),${END_ERR}p" "$ERR" > "$ERRTMP"

FULL=$(grep -c 'FULL_CYCLE_COMPLETE' "$OUTTMP" || true)
FAIL=$(grep -cE 'FULL_CYCLE_FAILED|CYCLE_FAILED|FAST_POSITION_TICK_FAILED' "$OUTTMP" || true)
EACCES=$(grep -c 'EACCES' "$ERRTMP" || true)
HTTP429=$(grep -cE 'HTTP 429|HTTP429' "$ERRTMP" || true)
ENTRYFAIL=$(grep -c 'ENTRY_FAIL ' "$OUTTMP" || true)
EXITFAIL=$(grep -c 'EXIT_QUOTE_FAIL ' "$OUTTMP" || true)

echo '=== V1.3.2 SOAK COUNTS ==='
echo "FULL_CYCLES=$FULL"
echo "CYCLE_FAILURES=$FAIL"
echo "EACCES=$EACCES"
echo "HTTP429=$HTTP429"
echo "ENTRY_FAIL=$ENTRYFAIL"
echo "EXIT_QUOTE_FAIL=$EXITFAIL"

[ "$FULL" -ge 1 ] || { echo 'NO_SUCCESSFUL_FULL_CYCLE'; tail -120 "$OUTTMP"; exit 1; }
[ "$FAIL" -eq 0 ] || { echo 'FULL_CYCLE_FAILURE_DETECTED'; tail -120 "$OUTTMP"; exit 1; }
[ "$EACCES" -eq 0 ] || { echo 'PERMISSION_REGRESSION_DETECTED'; tail -120 "$ERRTMP"; exit 1; }

node --input-type=module - <<'NODE'
import fs from 'node:fs';
const now=Date.now();
const c=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
const h=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/scanner-source-health.json','utf8'));
const r=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/risk-state.json','utf8'));
const s=JSON.parse(fs.readFileSync('/var/lib/meme-alpha/data/paper/stress-validation.json','utf8'));
const ha=(now-Date.parse(h.checkedAt||0))/1000;
const ra=(now-Date.parse(r.timestamp||0))/1000;
console.log(`SOURCE_STATUS=${h.status}`);
console.log(`SOURCE_AGE_SEC=${ha.toFixed(1)}`);
console.log(`RISK_AGE_SEC=${ra.toFixed(1)}`);
console.log(`RISK_VERSION=${r.version}`);
console.log(`STRESS_PASS=${s.summary?.pass ?? '?'} WARN=${s.summary?.warn ?? '?'} FAIL=${s.summary?.fail ?? '?'}`);
if(c.mode!=='PAPER') throw new Error('MODE_CHANGED');
if(h.status!=='HEALTHY'||h.usingCache===true||h.allowNewEntries!==true||ha>=180) throw new Error('SOURCE_HEALTH_BAD');
if(!Number.isFinite(ra)||ra>=120) throw new Error('RISK_STALE_AFTER_SOAK');
if(Number(s.summary?.fail||0)!==0) throw new Error('STRESS_INVARIANT_FAIL');
console.log('LIVE_EXECUTION=DISABLED');
console.log('V132_INVARIANT_PASS');
NODE

systemctl is-active "$SERVICE"
free -h
uptime
rm -f "$OUTTMP" "$ERRTMP"
echo 'V132_PERMISSION_FIX_PASS'
echo 'V130_OPERATIONAL_SOAK_PASS'
echo "BACKUP=$B"
