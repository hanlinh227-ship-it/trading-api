#!/usr/bin/env bash
set -euo pipefail

APP_HOME=/var/lib/trading/mt5-forex
AUTH_MARKER="$APP_HOME/broker-authenticated.marker"
RUNTIME_ENV="$APP_HOME/runtime.env"
PRIVATE_ENV=/etc/trading/mt5-forex.env
REPO=${FOREX_RESEARCH_REPO:-/opt/trading/trading-api-main}

source "$RUNTIME_ENV"
[[ -r "$PRIVATE_ENV" ]] && source "$PRIVATE_ENV"

: "${MT5_ACCOUNT_LOGIN:?missing MT5_ACCOUNT_LOGIN}"
: "${MT5_ACCOUNT_SERVER:?missing MT5_ACCOUNT_SERVER}"
: "${MT5_BRIDGE_TOKEN:?missing MT5_BRIDGE_TOKEN}"
HUB="${MT5_HUB_URL:-https://trading-v77-scanner.hanlinh227.workers.dev}"
PULSE="$MT5_INSTALL_DIR/MQL5/Files/FOREX_BRIDGE/pulse.json"
HEALTH="$APP_HOME/bridge-health.json"
EXPECTED_ID="${MT5_ACCOUNT_LOGIN}-${MT5_ACCOUNT_SERVER}"
LOCAL_TIMEOUT=${MT5_LOCAL_READY_TIMEOUT_SECONDS:-180}
SIDECAR_TIMEOUT=${MT5_SIDECAR_READY_TIMEOUT_SECONDS:-120}
HUB_TIMEOUT=${MT5_HUB_READY_TIMEOUT_SECONDS:-180}

pulse_diag() {
  python3 - "$PULSE" <<'PY' 2>/dev/null || true
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
if not p.is_file(): print('MT5_PULSE_DIAG=missing'); raise SystemExit
try: d=json.loads(p.read_text())
except Exception as e: print('MT5_PULSE_DIAG=json_error:'+repr(e)); raise SystemExit
m=d.get('mt5') if isinstance(d.get('mt5'),dict) else {}
a=d.get('account') if isinstance(d.get('account'),dict) else {}
print('MT5_PULSE_DIAG_TERMINAL_ID='+str(d.get('terminalId') or ''))
print('MT5_PULSE_DIAG_CONNECTED='+str(m.get('connected')))
print('MT5_PULSE_DIAG_TRADE_ALLOWED='+str(m.get('tradeAllowed')))
for k in ('balance','equity','margin','freeMargin'):
    v=a.get(k)
    try: print('MT5_PULSE_DIAG_'+k.upper()+'_POSITIVE='+str(float(v or 0)>0))
    except: print('MT5_PULSE_DIAG_'+k.upper()+'_POSITIVE=invalid')
PY
}

fail_diag() {
  echo "MT5_READINESS_DIAGNOSTICS_BEGIN" >&2
  pulse_diag >&2
  systemctl status mt5-forex.service mt5-forex-bridge.service --no-pager -l 2>/dev/null || true
  cat "$HEALTH" 2>/dev/null || true
  echo "MT5_READINESS_DIAGNOSTICS_END" >&2
}
trap 'rc=$?; if [[ $rc -ne 0 ]]; then fail_diag; fi' EXIT

systemctl is-active --quiet mt5-forex.service
systemctl is-active --quiet mt5-forex-bridge.service
# Detector fix (2026-08-27): Wine processes report comm == exe basename
# (e.g. "terminal64.exe"), never "main". Exact comm match, no args self-match.
ps -u mt5forex -o comm= 2>/dev/null | grep -qxF terminal64.exe
echo 'MT5_REAL_TERMINAL_PROCESS=PASS'

start=$(date +%s); last_report=0
while true; do
  systemctl is-active --quiet mt5-forex.service || exit 41
  systemctl is-active --quiet mt5-forex-bridge.service || exit 42
  if MT5_ACCOUNT_LOGIN="$MT5_ACCOUNT_LOGIN" MT5_ACCOUNT_SERVER="$MT5_ACCOUNT_SERVER" MT5_LOCAL_PULSE_MAX_AGE_SECONDS=180 python3 "$REPO/vps/mt5-forex/verify-local-pulse.py" "$PULSE" >/tmp/mt5-local-verify.log 2>&1; then
    cat /tmp/mt5-local-verify.log; break
  fi
  now=$(date +%s); elapsed=$((now-start))
  if (( elapsed-last_report >= 30 )); then echo "MT5_LOCAL_WAIT_SECONDS=$elapsed" >&2; cat /tmp/mt5-local-verify.log 2>/dev/null || true; pulse_diag >&2; last_report=$elapsed; fi
  (( elapsed < LOCAL_TIMEOUT )) || { echo "ERROR: local MT5 pulse readiness timeout after ${LOCAL_TIMEOUT}s" >&2; exit 43; }
  sleep 5
done

start=$(date +%s)
while true; do
  if python3 - "$HEALTH" "$EXPECTED_ID" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); expected=sys.argv[2]
if not p.is_file(): raise SystemExit(1)
try: d=json.loads(p.read_text())
except Exception: raise SystemExit(1)
if d.get('state')!='PULSE_FORWARDED': raise SystemExit(1)
if int(d.get('lastHttpStatus') or 0)!=200: raise SystemExit(1)
if str(d.get('terminalId') or '')!=expected: raise SystemExit(1)
if not d.get('lastSuccessAt'): raise SystemExit(1)
PY
  then echo "MT5_SIDECAR_TERMINAL_ID=$EXPECTED_ID"; echo 'MT5_SIDECAR_FORWARD=PASS'; break; fi
  now=$(date +%s); (( now-start < SIDECAR_TIMEOUT )) || { echo "ERROR: sidecar forwarding timeout" >&2; exit 44; }; sleep 3
done

BODY=$(mktemp)
trap 'rc=$?; rm -f "$BODY" /tmp/mt5-local-verify.log /tmp/mt5-hub-verify.log; if [[ $rc -ne 0 ]]; then fail_diag; fi' EXIT
start=$(date +%s)
while true; do
  code=$(curl -sS --connect-timeout 5 --max-time 20 -o "$BODY" -w '%{http_code}' "$HUB/forex/health" || true)
  if [[ "$code" == 200 ]] && MT5_ACCOUNT_LOGIN="$MT5_ACCOUNT_LOGIN" MT5_ACCOUNT_SERVER="$MT5_ACCOUNT_SERVER" MT5_HUB_PULSE_MAX_AGE_SECONDS=300 python3 "$REPO/vps/mt5-forex/verify-hub-pulse.py" "$BODY" >/tmp/mt5-hub-verify.log 2>&1; then cat /tmp/mt5-hub-verify.log; break; fi
  now=$(date +%s); (( now-start < HUB_TIMEOUT )) || { echo "ERROR: Hub pulse readiness timeout http=$code" >&2; exit 45; }; sleep 5
done

# Full broker/account readiness passed. From now on launch MT5 from the same
# persistent Wine prefix without re-injecting credentials on every restart.
printf 'login=%s\nserver=%s\nverified_at=%s\n' "$MT5_ACCOUNT_LOGIN" "$MT5_ACCOUNT_SERVER" "$(date -u +%FT%TZ)" >"$AUTH_MARKER"
chmod 0600 "$AUTH_MARKER"
echo 'MT5_BROKER_SESSION_PERSISTED=PASS'

case "${MT5_ALLOW_LIVE:-false}" in true|TRUE|1|yes|YES) echo 'MT5_LIVE_EXECUTION_REQUESTED=PASS' ;; *) echo 'MT5_LIVE_EXECUTION_REQUESTED=OFF' ;; esac
echo 'MT5_PULSE_FRESH=PASS'
echo 'MT5_CONNECTED=PASS'
echo 'MT5_ACCOUNT_LOGIN_MATCH=PASS'
echo 'MT5_ACCOUNT_SERVER_MATCH=PASS'
echo 'MT5_BALANCE_EQUITY=PASS'
echo 'MT5_FOREX_RUNTIME_READINESS=PASS'
