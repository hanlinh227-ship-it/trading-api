#!/usr/bin/env bash
set -euo pipefail

APP_HOME="/var/lib/trading/mt5-forex"
RUNTIME_ENV="$APP_HOME/runtime.env"
PRIVATE_ENV="/etc/trading/mt5-forex.env"
VPS_ONLY_MARKER="/etc/trading/mt5-forex-vps-only"
AUTH_MARKER="$APP_HOME/broker-authenticated.marker"
EXPECTED_HOST="${MT5_EXPECTED_HOST:-59670.vpsvinahost.vn}"

# Exit codes (systemd RestartPreventExitStatus relies on these):
#   9/10/11/12/15/91 = configuration/environment errors — restart cannot help
#   69 = terminal never appeared (launch failure)      — restart with backoff
#   70 = terminal exited after running (crash/close)   — restart with backoff

[[ -r "$VPS_ONLY_MARKER" ]] || { echo "ERROR: VPS-only marker missing" >&2; exit 9; }
CURRENT_FQDN="$(hostname -f 2>/dev/null || hostname)"; CURRENT_HOST="$(hostname 2>/dev/null || true)"
[[ "$CURRENT_FQDN" = "$EXPECTED_HOST" || "$CURRENT_HOST" = "${EXPECTED_HOST%%.*}" ]] || { echo "ERROR: unauthorized host" >&2; exit 91; }
[[ -r "$RUNTIME_ENV" ]] || { echo "ERROR: runtime.env missing" >&2; exit 10; }
source "$RUNTIME_ENV"; [[ -r "$PRIVATE_ENV" ]] && source "$PRIVATE_ENV"

: "${MT5_WINEPREFIX:?missing MT5_WINEPREFIX}"; : "${MT5_TERMINAL:?missing MT5_TERMINAL}"; : "${MT5_INSTALL_DIR:?missing MT5_INSTALL_DIR}"; : "${MT5_WINE_BIN:?missing MT5_WINE_BIN}"
MT5_ACCOUNT_LOGIN="${MT5_ACCOUNT_LOGIN:-}"
MT5_ACCOUNT_PASSWORD="${MT5_ACCOUNT_PASSWORD:-}"
MT5_ACCOUNT_SERVER="${MT5_ACCOUNT_SERVER:-}"
MT5_ACCOUNT_ENDPOINT="${MT5_ACCOUNT_ENDPOINT:-}"
MT5_HUB_URL="${MT5_HUB_URL:-https://trading-v77-scanner.hanlinh227.workers.dev}"
MT5_BRIDGE_TOKEN="${MT5_BRIDGE_TOKEN:-}"
MT5_ALLOW_LIVE="${MT5_ALLOW_LIVE:-false}"
MT5_SYMBOLS="${MT5_SYMBOLS:-EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD}"
MT5_TERMINAL_APPEAR_TIMEOUT="${MT5_TERMINAL_APPEAR_TIMEOUT:-90}"
case "${MT5_ALLOW_LIVE,,}" in true|1|yes) LIVE_BOOL=true; LIVE_INI=1 ;; *) LIVE_BOOL=false; LIVE_INI=0 ;; esac

PRESET="$MT5_INSTALL_DIR/MQL5/Presets/ForexAutoThe5ers.set"
BOOTSTRAP_CONFIG="$MT5_INSTALL_DIR/mt5-forex-bootstrap.ini"
BRIDGE_DIR="$MT5_INSTALL_DIR/MQL5/Files/FOREX_BRIDGE"
install -d -o mt5forex -g mt5forex -m 0750 "$BRIDGE_DIR" "$MT5_INSTALL_DIR/Config"
rm -f "$BRIDGE_DIR/decision.json" "$BRIDGE_DIR/decision.json.tmp" 2>/dev/null || true

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

SERVER_BOOTSTRAP="${MT5_ACCOUNT_ENDPOINT:-$MT5_ACCOUNT_SERVER}"
{
  echo '[Common]'
  [[ -n "$MT5_ACCOUNT_LOGIN" ]] && echo "Login=$MT5_ACCOUNT_LOGIN"
  [[ -n "$MT5_ACCOUNT_PASSWORD" ]] && echo "Password=$MT5_ACCOUNT_PASSWORD"
  [[ -n "$SERVER_BOOTSTRAP" ]] && echo "Server=$SERVER_BOOTSTRAP"
  echo 'ProxyEnable=0'
  echo 'KeepPrivate=1'
  echo 'NewsEnable=1'
  echo 'CertInstall=1'
  echo
  echo '[Experts]'
  echo 'Enabled=1'
  echo "AllowLiveTrading=$LIVE_INI"
  echo 'AllowDllImport=0'
  echo
  echo '[StartUp]'
  echo 'Expert=ForexAutoThe5ers'
  echo 'ExpertParameters=ForexAutoThe5ers.set'
  echo 'Symbol=EURUSD'
  echo 'Period=M5'
  echo 'ShutdownTerminal=0'
} >"$BOOTSTRAP_CONFIG"
chmod 0600 "$BOOTSTRAP_CONFIG"

if [[ "$LIVE_BOOL" == true ]]; then
  [[ -n "$MT5_ACCOUNT_LOGIN" && -n "$MT5_ACCOUNT_PASSWORD" && -n "$MT5_ACCOUNT_SERVER" ]] || { echo "ERROR: LIVE credentials incomplete" >&2; exit 11; }
  [[ -n "$MT5_BRIDGE_TOKEN" ]] || { echo "ERROR: bridge token missing" >&2; exit 12; }
fi

WINEPATH_BIN="${MT5_WINEPATH_BIN:-$(dirname "$MT5_WINE_BIN")/winepath}"
WINESERVER_BIN="${MT5_WINESERVER_BIN:-$(dirname "$MT5_WINE_BIN")/wineserver}"
CONFIG_WIN="$(HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINEPATH_BIN" -w "$BOOTSTRAP_CONFIG" 2>/dev/null || true)"
[[ -n "$CONFIG_WIN" ]] || { echo "ERROR: winepath failed" >&2; exit 15; }

HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINESERVER_BIN" -k >/dev/null 2>&1 || true
pkill -u "$(id -u)" -f 'terminal64.exe|metaeditor64.exe' 2>/dev/null || true
sleep 1

# ROOT CAUSE FIX (proven empirically 2026-08-27):
#   Previous launch: `wine start /wait <unix path>` — Wine's start.exe does NOT
#   accept Unix paths without the /unix switch; it printed its usage text and
#   exited, so terminal64.exe was NEVER launched. Every cycle then burned the
#   full appear-timeout and exited 69 → systemd restart loop (~45-50s/cycle).
#   Fix: launch the terminal directly with `wine "$MT5_TERMINAL"`. The wine
#   wrapper process lives exactly as long as the terminal, so we can wait on it.
#
#   Previous detector: awk '$1=="main" && index($0,"terminal64.exe")' — Wine
#   processes appear in `ps -o comm=` with comm == the exe basename
#   (e.g. "terminal64.exe"), never "main". The detector could not match a
#   living terminal and would have killed a healthy session at the timeout.
#   Fix: exact comm match on the terminal basename via `ps -o comm=` + grep -qxF.
#   The basename is passed via env so the monitor's own argv never contains
#   the literal exe name (prevents pgrep/args self-match false positives).
if [[ -f "$AUTH_MARKER" ]]; then
  LAUNCH_MODE="PERSISTENT_SESSION"
  LAUNCH_ARGS=("$MT5_TERMINAL")
else
  LAUNCH_MODE="BOOTSTRAP_AUTH"
  LAUNCH_ARGS=("$MT5_TERMINAL" "/config:$CONFIG_WIN")
fi

echo 'MT5_FOREX_START=PASS'
echo 'MT5_FOREX_ARCHITECTURE=PERSISTENT_APPLIANCE'
echo "MT5_FOREX_LAUNCH_MODE=$LAUNCH_MODE"
echo "MT5_FOREX_MODE=$([[ "$LIVE_BOOL" == true ]] && echo LIVE || echo PAPER)"
echo "MT5_FOREX_AUTH_STATE=$([[ -f "$AUTH_MARKER" ]] && echo PERSISTED || echo BOOTSTRAP_REQUIRED)"
echo "MT5_FOREX_SERVER_BOOTSTRAP_SOURCE=$([[ -n "$MT5_ACCOUNT_ENDPOINT" ]] && echo ENDPOINT || echo DISPLAY_NAME)"
echo "MT5_FOREX_WINE_VERSION=${MT5_WINE_VERSION:-UNKNOWN}"

TERM_BASENAME="$(basename "$MT5_TERMINAL")"
export APP_HOME MT5_WINEPREFIX MT5_WINE_BIN LAUNCH_MODE TERM_BASENAME MT5_TERMINAL_APPEAR_TIMEOUT
printf -v CMD '%q ' "${LAUNCH_ARGS[@]}"
export CMD
exec xvfb-run -a -s '-screen 0 1280x1024x24' bash -c '
  set +e
  LOG="$APP_HOME/wine-terminal-launch.log"
  : > "$LOG"
  echo "MT5_FOREX_EXEC_MODE=$LAUNCH_MODE"
  # Direct execution: the wine process IS the terminal lifetime.
  HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" WINEDEBUG=-all "$MT5_WINE_BIN" $CMD >>"$LOG" 2>&1 &
  wine_pid=$!

  term_alive() { ps -u "$(id -u)" -o comm= | grep -qxF "$TERM_BASENAME"; }
  dump_diag() {
    echo "MT5_FOREX_DIAG_PS_SNAPSHOT_BEGIN"
    ps -u "$(id -u)" -o comm=,args= | grep -vE "^(ps|grep|bash|xvfb|Xvfb|awk) " | head -30
    echo "MT5_FOREX_DIAG_PS_SNAPSHOT_END"
    echo "MT5_FOREX_DIAG_WINE_LOG_TAIL_BEGIN"
    tail -40 "$LOG" 2>/dev/null
    echo "MT5_FOREX_DIAG_WINE_LOG_TAIL_END"
  }

  appeared=false
  launcher_died=false
  for i in $(seq 1 "$MT5_TERMINAL_APPEAR_TIMEOUT"); do
    if term_alive; then appeared=true; break; fi
    if ! kill -0 "$wine_pid" >/dev/null 2>&1; then launcher_died=true; break; fi
    sleep 1
  done

  if [[ "$appeared" != true ]]; then
    echo "MT5_FOREX_TERMINAL_APPEAR=FAIL"
    [[ "$launcher_died" == true ]] && echo "MT5_FOREX_LAUNCHER_EXITED_EARLY=1"
    dump_diag
    exit 69
  fi

  echo "MT5_FOREX_REAL_TERMINAL_PROCESS=PASS"
  # Monitor: terminal alive as long as its comm is present OR the wine wrapper runs.
  while term_alive || kill -0 "$wine_pid" >/dev/null 2>&1; do sleep 5; done
  echo "MT5_FOREX_TERMINAL_EXITED=1"
  dump_diag
  exit 70
'
