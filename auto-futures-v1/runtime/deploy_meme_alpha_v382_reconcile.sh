#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" -eq 0 ]] || { echo 'MEME_V382_RECONCILE=DEFER_NOT_ROOT'; exit 0; }

APP=/opt/meme-alpha/app
EXECUTOR="$APP/src/micro-live-executor.js"
GATE="$APP/runtime-status/micro-live-gate.json"
ARM=/etc/meme-alpha/micro-live-armed
DONE=/var/lib/meme-alpha/v382-root-reconciled.json
LOCK=/tmp/meme-alpha-v382-reconcile.lock

exec 7>"$LOCK"
if ! flock -n 7; then echo 'MEME_V382_RECONCILE=DEFER_LOCK_BUSY'; exit 0; fi

[[ -f "$EXECUTOR" ]] || { echo 'MEME_V382_RECONCILE=DEFER_EXECUTOR_MISSING'; exit 0; }
grep -q 'MICRO_LIVE_EXECUTOR_V382_NO_SOFT_GATE_FAST_PIPELINE=STARTED' "$EXECUTOR" || { echo 'MEME_V382_RECONCILE=DEFER_NOT_V382'; exit 0; }

# Explicit manual disarm always wins. Never auto-override ARMED=NO.
ARM_VALUE=""
if [[ -f "$ARM" ]]; then ARM_VALUE="$(cat "$ARM" 2>/dev/null || true)"; fi
if [[ "$ARM_VALUE" == 'ARMED=NO' ]]; then
  echo 'MEME_V382_RECONCILE=DEFER_EXPLICIT_DISARM'
  exit 0
fi

# Normal steady state: one-time reconcile was completed and root ARM still exists.
if [[ -f "$DONE" && "$ARM_VALUE" == 'ARMED=YES' ]]; then
  echo 'MEME_V382_RECONCILE=ALREADY_COMPLETED_ARM_HEALTHY'
  exit 0
fi

# If DONE exists but ARM disappeared (or was replaced by the legacy maintenance marker),
# treat it as drift/corruption rather than an intentional disarm and allow a bounded repair.
# Unknown non-empty states remain fail-closed.
if [[ -n "$ARM_VALUE" && "$ARM_VALUE" != 'ARMED=YES' && "$ARM_VALUE" != 'MAINTENANCE=V377' ]]; then
  echo "MEME_V382_RECONCILE=DEFER_UNKNOWN_ARM_STATE value=$ARM_VALUE"
  exit 0
fi

for u in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service; do
  systemctl is-active --quiet "$u" || { echo "MEME_V382_RECONCILE=DEFER_SERVICE unit=$u"; exit 0; }
done

# Require existing signer/source/risk checks to be healthy before any root ARM repair.
python3 - "$GATE" <<'PY'
import json,sys
p=sys.argv[1]
try: g=json.load(open(p))
except Exception: raise SystemExit(2)
assert g.get('sourceHealthy') is True
assert g.get('riskEntryAllowed') is True
assert g.get('liveRiskReady') is True
s=g.get('signer') or {}
assert s.get('ok') is True and s.get('mode')=='READY'
assert s.get('signingEnabled') is True and s.get('walletLoaded') is True
assert s.get('arbitraryRawSign') is False
PY

mkdir -p /etc/meme-alpha
chown root:meme-alpha-signer-client /etc/meme-alpha
chmod 0750 /etc/meme-alpha
TMP="$(mktemp /tmp/meme-alpha-v382-arm.XXXXXX)"
printf 'ARMED=YES\n' > "$TMP"
install -o root -g meme-alpha-signer-client -m 0640 "$TMP" "$ARM"
rm -f "$TMP"

# Verify the root-owned control immediately before restarting execution.
[[ "$(cat "$ARM")" == 'ARMED=YES' ]] || { echo 'MEME_V382_RECONCILE=DEFER_ARM_WRITE_VERIFY'; exit 0; }
[[ "$(stat -c %u "$ARM")" == '0' ]] || { echo 'MEME_V382_RECONCILE=DEFER_ARM_OWNER_VERIFY'; exit 0; }
[[ "$(stat -c %a "$ARM")" == '640' ]] || { echo 'MEME_V382_RECONCILE=DEFER_ARM_MODE_VERIFY'; exit 0; }

systemctl restart meme-alpha-micro-live.service
sleep 3
systemctl is-active --quiet meme-alpha-micro-live.service
systemctl restart meme-alpha-paper.service

READY=0
for _ in $(seq 1 45); do
  if [[ -f "$GATE" ]] && python3 - "$GATE" <<'PY'
import json,sys,time,datetime
try:g=json.load(open(sys.argv[1]))
except Exception:raise SystemExit(1)
ts=g.get('timestamp') or ''
age=time.time()-datetime.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp() if ts else 999
assert age < 30
assert g.get('allowed') is True
assert g.get('armOk') is True
assert g.get('armAttested') is True
assert g.get('executionMode') == 'MICRO_LIVE'
assert g.get('sourceHealthy') is True
assert g.get('riskEntryAllowed') is True
assert g.get('liveRiskReady') is True
assert not (g.get('riskGlobalBlockReasons') or [])
assert not (g.get('riskLiveBlockReasons') or [])
assert not (g.get('reasons') or [])
PY
  then READY=1; break; fi
  sleep 2
done
[[ "$READY" -eq 1 ]] || { echo 'MEME_V382_RECONCILE=DEFER_GATE_VERIFY'; exit 0; }

mkdir -p "$(dirname "$DONE")"
printf '{"version":"3.82","status":"ROOT_RECONCILED_AND_SELF_HEALED","timestamp":"%s","armRepair":true}\n' "$(date -u +%FT%TZ)" > "$DONE"
chmod 0600 "$DONE"
echo 'MEME_V382_RECONCILE=SUCCESS_ARM_REPAIRED'
