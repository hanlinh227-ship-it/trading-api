#!/usr/bin/env bash
set -euo pipefail

APP_HOME="/var/lib/trading/mt5-forex"
RUNTIME_ENV="$APP_HOME/runtime.env"
PRIVATE_ENV="/etc/trading/mt5-forex.env"
VPS_ONLY_MARKER="/etc/trading/mt5-forex-vps-only"
EXPECTED_HOST="${MT5_EXPECTED_HOST:-59670.vpsvinahost.vn}"

if [[ ! -r "$VPS_ONLY_MARKER" ]]; then echo "ERROR: VPS-only marker missing; MT5 launch refused" >&2; exit 9; fi
CURRENT_FQDN="$(hostname -f 2>/dev/null || hostname)"; CURRENT_HOST="$(hostname 2>/dev/null || true)"
if [[ "$CURRENT_FQDN" != "$EXPECTED_HOST" && "$CURRENT_HOST" != "${EXPECTED_HOST%%.*}" ]]; then echo "ERROR: MT5 launch refused outside authorized trading VPS" >&2; exit 91; fi
if [[ ! -r "$RUNTIME_ENV" ]]; then echo "ERROR: MT5 runtime.env missing; run install-mt5-forex.sh first" >&2; exit 10; fi
source "$RUNTIME_ENV"
if [[ -r "$PRIVATE_ENV" ]]; then source "$PRIVATE_ENV"; fi

: "${MT5_WINEPREFIX:?missing MT5_WINEPREFIX}"
: "${MT5_TERMINAL:?missing MT5_TERMINAL}"
: "${MT5_INSTALL_DIR:?missing MT5_INSTALL_DIR}"
: "${MT5_WINE_BIN:?missing MT5_WINE_BIN}"
test -d "$MT5_WINEPREFIX"; test -f "$MT5_TERMINAL"; test -d "$MT5_INSTALL_DIR"

MT5_ACCOUNT_LOGIN="${MT5_ACCOUNT_LOGIN:-}"
MT5_ACCOUNT_PASSWORD="${MT5_ACCOUNT_PASSWORD:-}"
MT5_ACCOUNT_SERVER="${MT5_ACCOUNT_SERVER:-}"
MT5_HUB_URL="${MT5_HUB_URL:-https://trading-v77-scanner.hanlinh227.workers.dev}"
MT5_BRIDGE_TOKEN="${MT5_BRIDGE_TOKEN:-}"
MT5_ALLOW_LIVE="${MT5_ALLOW_LIVE:-false}"
MT5_SYMBOLS="${MT5_SYMBOLS:-EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD}"
case "${MT5_ALLOW_LIVE,,}" in true|1|yes) LIVE_BOOL=true; LIVE_INI=1 ;; *) LIVE_BOOL=false; LIVE_INI=0 ;; esac

PRESET="$MT5_INSTALL_DIR/MQL5/Presets/ForexAutoThe5ers.set"
CONFIG="$MT5_INSTALL_DIR/mt5-forex-start.ini"
DEFAULT_CONFIG="$MT5_INSTALL_DIR/Config/common.ini"
BRIDGE_DIR="$MT5_INSTALL_DIR/MQL5/Files/FOREX_BRIDGE"
install -d -o mt5forex -g mt5forex -m 0750 "$BRIDGE_DIR" "$MT5_INSTALL_DIR/Config"
rm -f "$BRIDGE_DIR/decision.json" "$BRIDGE_DIR/decision.json.tmp" "$BRIDGE_DIR/pulse.json" 2>/dev/null || true

cat >"$PRESET" <<EOF
InpHubUrl=$MT5_HUB_URL
InpBridgeToken=$MT5_BRIDGE_TOKEN
InpAllowLiveTrading=$LIVE_BOOL
InpPulseSeconds=60
InpMaxRiskPct=1.00
InpMinFreeMarginPct=35.0
InpMinMarginLevelPct=300.0
InpMagic=560501
InpSymbols=$MT5_SYMBOLS
InpBreakEvenR=1.00
InpProfitLockR=1.35
InpTrailR=1.60
EOF
chmod 0600 "$PRESET"

write_config(){
  local out="$1"
  {
    echo '[Common]'
    [[ -n "$MT5_ACCOUNT_LOGIN" ]] && echo "Login=$MT5_ACCOUNT_LOGIN"
    [[ -n "$MT5_ACCOUNT_PASSWORD" ]] && echo "Password=$MT5_ACCOUNT_PASSWORD"
    [[ -n "$MT5_ACCOUNT_SERVER" ]] && echo "Server=$MT5_ACCOUNT_SERVER"
    echo 'ProxyEnable=0'
    echo 'KeepPrivate=1'
    echo 'NewsEnable=1'
    echo 'CertInstall=1'
    echo
    echo '[Charts]'
    echo 'MaxBars=100000'
    echo
    echo '[Experts]'
    echo 'Enabled=1'
    echo "AllowLiveTrading=$LIVE_INI"
    echo 'AllowDllImport=0'
    echo 'Account=0'
    echo 'Profile=0'
    echo
    echo '[StartUp]'
    echo 'Expert=ForexAutoThe5ers'
    echo 'ExpertParameters=ForexAutoThe5ers.set'
    echo 'Symbol=EURUSD'
    echo 'Period=M5'
    echo 'ShutdownTerminal=0'
  } >"$out"
  chmod 0600 "$out"
}
write_config "$CONFIG"
write_config "$DEFAULT_CONFIG"

if [[ "$LIVE_BOOL" == true ]]; then
  if [[ -z "$MT5_ACCOUNT_LOGIN" || -z "$MT5_ACCOUNT_PASSWORD" || -z "$MT5_ACCOUNT_SERVER" ]]; then echo "ERROR: LIVE requested but broker credentials are incomplete" >&2; exit 11; fi
  if [[ -z "$MT5_BRIDGE_TOKEN" || -z "$MT5_HUB_URL" ]]; then echo "ERROR: LIVE requested but MT5 bridge configuration is incomplete" >&2; exit 12; fi
fi

WINEPATH_BIN="${MT5_WINEPATH_BIN:-$(dirname "$MT5_WINE_BIN")/winepath}"
WINESERVER_BIN="${MT5_WINESERVER_BIN:-$(dirname "$MT5_WINE_BIN")/wineserver}"
[[ -x "$WINEPATH_BIN" ]] || { echo "ERROR: pinned winepath missing" >&2; exit 13; }
[[ -x "$WINESERVER_BIN" ]] || { echo "ERROR: pinned wineserver missing" >&2; exit 14; }
CONFIG_WIN="$(HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINEPATH_BIN" -w "$CONFIG" 2>/dev/null || true)"
[[ -n "$CONFIG_WIN" ]] || { echo "ERROR: winepath failed for MT5 config" >&2; exit 15; }

echo "MT5_FOREX_START=PASS"
echo "MT5_FOREX_RUNTIME_SCOPE=VPS_ONLY"
echo "MT5_FOREX_HOST_AUTHORIZED=PASS"
echo "MT5_FOREX_MODE=$([[ "$LIVE_BOOL" == true ]] && echo LIVE || echo PAPER)"
echo "MT5_FOREX_CREDENTIALS=$([[ -n "$MT5_ACCOUNT_LOGIN" && -n "$MT5_ACCOUNT_PASSWORD" && -n "$MT5_ACCOUNT_SERVER" ]] && echo CONFIGURED || echo INCOMPLETE)"
echo "MT5_FOREX_WINE_STACK=${MT5_WINE_STACK:-UNKNOWN}"
echo "MT5_FOREX_WINE_VERSION=${MT5_WINE_VERSION:-UNKNOWN}"
echo "MT5_FOREX_TRANSPORT=LOCAL_SIDECAR"

export APP_HOME MT5_WINEPREFIX MT5_WINE_BIN MT5_TERMINAL CONFIG_WIN WINESERVER_BIN MT5_ACCOUNT_LOGIN MT5_INSTALL_DIR
exec xvfb-run -a -s '-screen 0 1280x1024x24' bash -c '
  set +e
  args=("$MT5_TERMINAL" /portable "/config:$CONFIG_WIN")
  if [ -n "$MT5_ACCOUNT_LOGIN" ]; then args+=("/login:$MT5_ACCOUNT_LOGIN"); fi

  HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" WINEDEBUG=-all "$MT5_WINE_BIN" "${args[@]}"
  launcher_rc=$?
  echo "MT5_FOREX_WINE_LAUNCHER_EXIT=$launcher_rc"

  # Never use pgrep -f here: the supervisor command line itself contains the
  # string terminal64.exe and can create a false-positive detached-terminal PASS.
  terminal_alive=false
  for i in $(seq 1 20); do
    if pgrep -u "$(id -u)" -x terminal64.exe >/dev/null 2>&1; then
      terminal_alive=true
      break
    fi
    sleep 1
  done

  if [ "$terminal_alive" = true ]; then
    echo "MT5_FOREX_DETACHED_TERMINAL=PASS"
    echo "MT5_FOREX_LAUNCHER_RC_IGNORED=$launcher_rc"
    while pgrep -u "$(id -u)" -x terminal64.exe >/dev/null 2>&1; do
      sleep 5
    done
    echo "MT5_FOREX_TERMINAL_EXITED=1"
    HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINESERVER_BIN" -k >/dev/null 2>&1 || true
    exit 69
  fi

  if [ "$launcher_rc" -ne 0 ]; then
    echo "MT5_FOREX_RUNTIME_DIAGNOSTICS_BEGIN"
    echo "MT5_FOREX_REAL_TERMINAL_PROCESS=ABSENT"
    ps -u "$(id -u)" -o pid=,comm=,args= 2>/dev/null | tail -n 80 || true
    find "$MT5_INSTALL_DIR/Logs" "$MT5_INSTALL_DIR/MQL5/Logs" -maxdepth 1 -type f 2>/dev/null -printf "%T@ %p\n" | sort -nr | head -n 8 | cut -d" " -f2- | while IFS= read -r f; do
      echo "--- ${f##*/} ---"
      tail -n 120 "$f" 2>/dev/null | sed -E "s/[0-9]{6,}/[REDACTED_NUMBER]/g" || true
    done
    echo "MT5_FOREX_RUNTIME_DIAGNOSTICS_END"
  fi

  HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINESERVER_BIN" -w
  wait_rc=$?
  if [ "$wait_rc" -ne 0 ]; then exit "$wait_rc"; fi
  exit "$launcher_rc"
'