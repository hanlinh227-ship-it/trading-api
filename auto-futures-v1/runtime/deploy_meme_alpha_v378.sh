#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V378_DEPLOY=DEFER_NOT_ROOT'; exit 0; }
APP=/opt/meme-alpha/app
EXECUTOR="$APP/src/micro-live-executor.js"
PATCHER=/opt/trading/trading-api/auto-futures-v1/runtime/meme_alpha_patch_v378.py
BACKUP_ROOT=/opt/meme-alpha/backups
LOCK=/tmp/meme-alpha-v378-deploy.lock
ARM=/etc/meme-alpha/micro-live-armed
GATE="$APP/runtime-status/micro-live-gate.json"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$BACKUP_ROOT/v378_$TS"
TMP="$(mktemp -d /tmp/meme-alpha-v378.XXXXXX)"
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT
exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V378_DEPLOY=DEFER_LOCK_BUSY'; exit 0; fi
for f in "$EXECUTOR" "$PATCHER"; do [[ -f "$f" ]] || { echo "MEME_V378_DEPLOY=DEFER_MISSING_FILE name=$(basename "$f")"; exit 0; }; done

# V381 root activation reconcile. This does not weaken any trading gate: it only
# restores the root-owned arm when all existing live safety prerequisites are
# already healthy. Candidate-level security/holder/insider/sellability gates
# remain enforced by the executor and signer.
if grep -q 'MICRO_LIVE_EXECUTOR_V381_FAST_CAPITAL_ROTATION' "$EXECUTOR"; then
  for u in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-realtime-pulse.service meme-alpha-trend-pulse.service meme-alpha-whale-flow.service; do
    systemctl is-active --quiet "$u" || { echo "MEME_V381_ARM=DEFER_SERVICE unit=$u"; exit 0; }
  done
  python3 - "$GATE" <<'PY'
import json,sys,time,datetime,os
p=sys.argv[1]
try:
 d=json.load(open(p))
except Exception:
 raise SystemExit(2)
assert d.get('executionMode') == 'MICRO_LIVE'
assert d.get('signer',{}).get('ok') is True
assert d.get('signer',{}).get('mode') == 'READY'
assert d.get('signer',{}).get('signingEnabled') is True
assert d.get('signer',{}).get('walletLoaded') is True
assert d.get('signer',{}).get('arbitraryRawSign') is False
assert d.get('sourceHealthy') is True
assert d.get('riskEntryAllowed') is True
assert d.get('liveRiskReady') is True
assert not (d.get('riskGlobalBlockReasons') or [])
assert not (d.get('riskLiveBlockReasons') or [])
ts=d.get('timestamp')
assert ts
age=time.time()-datetime.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
assert age < 90, age
PY
  mkdir -p "$(dirname "$ARM")"
  T="$(mktemp /tmp/meme-alpha-arm-v381.XXXXXX)"
  printf 'ARMED=YES\n' > "$T"
  install -o root -g root -m 0640 "$T" "$ARM"
  rm -f "$T"
  systemctl restart meme-alpha-micro-live.service
  sleep 3
  systemctl is-active --quiet meme-alpha-micro-live.service
  OK=0
  for _ in $(seq 1 20); do
    if python3 - "$GATE" <<'PY'
import json,sys,time,datetime
try:d=json.load(open(sys.argv[1]))
except Exception:raise SystemExit(1)
ts=d.get('timestamp') or ''
try: age=time.time()-datetime.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
except Exception: age=999
ok=(d.get('allowed') is True and d.get('armOk') is True and d.get('armAttested') is True and d.get('executionMode')=='MICRO_LIVE' and age<30 and not (d.get('reasons') or []))
raise SystemExit(0 if ok else 1)
PY
    then OK=1; break; fi
    sleep 1
  done
  [[ "$OK" -eq 1 ]] || { echo 'MEME_V381_ARM=FAIL_GATE_NOT_ALLOWED'; exit 1; }
  echo 'MEME_V381_ARM=ACTIVE'
  exit 0
fi

# v3.79 is a strict successor of v3.78. Never downgrade a live v3.79 executor
# when this legacy root hook is invoked only to reconcile an older maintenance state.
if grep -q 'MICRO_LIVE_EXECUTOR_V379_HIGH_OPPORTUNITY' "$EXECUTOR"; then echo 'MEME_V378_DEPLOY=ALREADY_SUPERSEDED_BY_V379'; exit 0; fi
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
