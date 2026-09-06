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

# Root activation reconcile for v3.81+ successors. Never downgrade a newer
# executor. Root arm is restored only while the existing fail-closed live
# prerequisites are healthy. Candidate-level hard safety remains untouched.
if grep -Eq 'MICRO_LIVE_EXECUTOR_V38[1-9]|V381_FAST_CAPITAL' "$EXECUTOR"; then
  for u in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service meme-alpha-realtime-pulse.service meme-alpha-trend-pulse.service meme-alpha-whale-flow.service; do
    systemctl is-active --quiet "$u" || { echo "MEME_V38X_ARM=DEFER_SERVICE unit=$u"; exit 0; }
  done

  # Explicit manual disarm always wins. Missing/stale/legacy state may be
  # repaired only after signer/source/risk preconditions pass below.
  if [[ -f "$ARM" ]]; then
    ARM_VALUE="$(cat "$ARM" 2>/dev/null || true)"
    if [[ "$ARM_VALUE" == 'ARMED=NO' ]]; then
      echo 'MEME_V38X_ARM=DEFER_EXPLICIT_DISARM'
      exit 0
    fi
    if [[ -n "$ARM_VALUE" && "$ARM_VALUE" != 'ARMED=YES' && "$ARM_VALUE" != 'MAINTENANCE=V377' ]]; then
      echo "MEME_V38X_ARM=DEFER_UNKNOWN_STATE value=$ARM_VALUE"
      exit 0
    fi
  fi

  python3 - "$GATE" <<'PY'
import json,sys,time,datetime
p=sys.argv[1]
d=json.load(open(p))
assert d.get('executionMode') == 'MICRO_LIVE'
s=d.get('signer',{})
assert s.get('ok') is True and s.get('mode') == 'READY'
assert s.get('signingEnabled') is True and s.get('walletLoaded') is True
assert s.get('arbitraryRawSign') is False
assert d.get('sourceHealthy') is True
assert d.get('riskEntryAllowed') is True
assert d.get('liveRiskReady') is True
assert not (d.get('riskGlobalBlockReasons') or [])
assert not (d.get('riskLiveBlockReasons') or [])
ts=d.get('timestamp'); assert ts
age=time.time()-datetime.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
assert age < 90, age
PY

  # micro-live runs unprivileged. The old root:root 0640 handoff made a valid
  # ARMED=YES file unreadable and was therefore reported as absent/invalid.
  # Restore the known-good signer-client group ownership used by v3.79+.
  mkdir -p "$(dirname "$ARM")"
  chown root:meme-alpha-signer-client "$(dirname "$ARM")"
  chmod 0750 "$(dirname "$ARM")"
  NEED_ARM_REPAIR=1
  if [[ -f "$ARM" ]] && [[ "$(cat "$ARM" 2>/dev/null || true)" == 'ARMED=YES' ]] \
     && [[ "$(stat -c %U "$ARM" 2>/dev/null || true)" == 'root' ]] \
     && [[ "$(stat -c %G "$ARM" 2>/dev/null || true)" == 'meme-alpha-signer-client' ]] \
     && [[ "$(stat -c %a "$ARM" 2>/dev/null || true)" == '640' ]]; then
    NEED_ARM_REPAIR=0
  fi
  if [[ "$NEED_ARM_REPAIR" -eq 1 ]]; then
    T="$(mktemp /tmp/meme-alpha-arm-v38x.XXXXXX)"
    printf 'ARMED=YES\n' > "$T"
    install -o root -g meme-alpha-signer-client -m 0640 "$T" "$ARM"
    rm -f "$T"
    echo 'MEME_V38X_ARM_FILE=REPAIRED'
  else
    echo 'MEME_V38X_ARM_FILE=VALID'
  fi

  systemctl restart meme-alpha-micro-live.service
  sleep 3
  systemctl is-active --quiet meme-alpha-micro-live.service
  OK=0
  for _ in $(seq 1 25); do
    if python3 - "$GATE" <<'PY'
import json,sys,time,datetime
d=json.load(open(sys.argv[1]))
ts=d.get('timestamp') or ''
try: age=time.time()-datetime.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()
except Exception: age=999
ok=(d.get('allowed') is True and d.get('armOk') is True and d.get('armAttested') is True and d.get('executionMode')=='MICRO_LIVE' and d.get('sourceHealthy') is True and d.get('riskEntryAllowed') is True and d.get('liveRiskReady') is True and not (d.get('riskGlobalBlockReasons') or []) and not (d.get('riskLiveBlockReasons') or []) and not (d.get('reasons') or []) and age<30)
raise SystemExit(0 if ok else 1)
PY
    then OK=1; break; fi
    sleep 1
  done
  [[ "$OK" -eq 1 ]] || { echo 'MEME_V38X_ARM=FAIL_GATE_NOT_ALLOWED'; exit 1; }
  echo 'MEME_V38X_ARM=ACTIVE'
  exit 0
fi

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
