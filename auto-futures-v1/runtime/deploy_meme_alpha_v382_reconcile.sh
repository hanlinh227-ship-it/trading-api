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

# This is intentionally a one-time reconcile. Once completed, a later manual
# disarm is never overridden by the periodic root updater.
if [[ -f "$DONE" ]]; then
  echo 'MEME_V382_RECONCILE=ALREADY_COMPLETED'
  exit 0
fi

for u in meme-alpha-paper.service meme-alpha-micro-live.service meme-alpha-signer.service; do
  systemctl is-active --quiet "$u" || { echo "MEME_V382_RECONCILE=DEFER_SERVICE unit=$u"; exit 0; }
done

# Require the existing risk/source checks to be healthy before one-time arming.
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

# If an explicit ARMED=NO exists, treat it as an intentional manual disarm and
# never override it. Missing/invalid legacy state is repaired only for this
# explicitly authorized v3.82 activation.
if [[ -f "$ARM" ]]; then
  V="$(cat "$ARM" 2>/dev/null || true)"
  if [[ "$V" == 'ARMED=NO' ]]; then
    echo 'MEME_V382_RECONCILE=DEFER_EXPLICIT_DISARM'
    exit 0
  fi
  if [[ -n "$V" && "$V" != 'ARMED=YES' && "$V" != 'MAINTENANCE=V377' ]]; then
    echo "MEME_V382_RECONCILE=DEFER_UNKNOWN_ARM_STATE value=$V"
    exit 0
  fi
fi

mkdir -p /etc/meme-alpha
chown root:meme-alpha-signer-client /etc/meme-alpha
chmod 0750 /etc/meme-alpha
TMP="$(mktemp /tmp/meme-alpha-v382-arm.XXXXXX)"
printf 'ARMED=YES\n' > "$TMP"
install -o root -g meme-alpha-signer-client -m 0640 "$TMP" "$ARM"
rm -f "$TMP"

systemctl restart meme-alpha-micro-live.service
sleep 3
systemctl is-active --quiet meme-alpha-micro-live.service
systemctl restart meme-alpha-paper.service

READY=0
for _ in $(seq 1 30); do
  if [[ -f "$GATE" ]] && python3 - "$GATE" <<'PY'
import json,sys
try:g=json.load(open(sys.argv[1]))
except Exception:raise SystemExit(1)
assert g.get('allowed') is True
assert g.get('armOk') is True
assert g.get('sourceHealthy') is True
assert g.get('riskEntryAllowed') is True
assert g.get('liveRiskReady') is True
PY
  then READY=1; break; fi
  sleep 2
done
[[ "$READY" -eq 1 ]] || { echo 'MEME_V382_RECONCILE=DEFER_GATE_VERIFY'; exit 0; }

mkdir -p "$(dirname "$DONE")"
printf '{"version":"3.82","status":"ROOT_RECONCILED_ONCE","timestamp":"%s"}\n' "$(date -u +%FT%TZ)" > "$DONE"
chmod 0600 "$DONE"
echo 'MEME_V382_RECONCILE=SUCCESS'
