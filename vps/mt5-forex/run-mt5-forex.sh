#!/usr/bin/env bash
set -euo pipefail

APP_HOME="/var/lib/trading/mt5-forex"
RUNTIME_ENV="$APP_HOME/runtime.env"
PRIVATE_ENV="/etc/trading/mt5-forex.env"
VPS_ONLY_MARKER="/etc/trading/mt5-forex-vps-only"
EXPECTED_HOST="${MT5_EXPECTED_HOST:-59670.vpsvinahost.vn}"

if [[ ! -r "$VPS_ONLY_MARKER" ]]; then
  echo "ERROR: VPS-only marker missing; MT5 launch refused" >&2
  exit 9
fi

CURRENT_FQDN="$(hostname -f 2>/dev/null || hostname)"
CURRENT_HOST="$(hostname 2>/dev/null || true)"
if [[ "$CURRENT_FQDN" != "$EXPECTED_HOST" && "$CURRENT_HOST" != "${EXPECTED_HOST%%.*}" ]]; then
  echo "ERROR: MT5 launch refused outside authorized trading VPS" >&2
  exit 91
fi

if [[ ! -r "$RUNTIME_ENV" ]]; then
  echo "ERROR: MT5 runtime.env missing; run install-mt5-forex.sh first" >&2
  exit 10
fi
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
if [[ -r "$PRIVATE_ENV" ]]; then
  # shellcheck disable=SC1090
  source "$PRIVATE_ENV"
fi

: "${MT5_WINEPREFIX:?missing MT5_WINEPREFIX}"
: "${MT5_TERMINAL:?missing MT5_TERMINAL}"
: "${MT5_INSTALL_DIR:?missing MT5_INSTALL_DIR}"
: "${MT5_WINE_BIN:?missing MT5_WINE_BIN}"

test -d "$MT5_WINEPREFIX"
test -f "$MT5_TERMINAL"
test -d "$MT5_INSTALL_DIR"

MT5_ACCOUNT_LOGIN="${MT5_ACCOUNT_LOGIN:-}"
MT5_ACCOUNT_PASSWORD="${MT5_ACCOUNT_PASSWORD:-}"
MT5_ACCOUNT_SERVER="${MT5_ACCOUNT_SERVER:-}"
MT5_HUB_URL="${MT5_HUB_URL:-https://trading-v77-scanner.hanlinh227.workers.dev}"
MT5_BRIDGE_TOKEN="${MT5_BRIDGE_TOKEN:-}"
MT5_ALLOW_LIVE="${MT5_ALLOW_LIVE:-false}"
MT5_SYMBOLS="${MT5_SYMBOLS:-EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD,EURJPY,GBPJPY,EURGBP,XAUUSD}"

case "${MT5_ALLOW_LIVE,,}" in
  true|1|yes) LIVE_BOOL=true; LIVE_INI=1 ;;
  *) LIVE_BOOL=false; LIVE_INI=0 ;;
esac

PRESET="$MT5_INSTALL_DIR/MQL5/Presets/ForexAutoThe5ers.set"
CONFIG="$MT5_INSTALL_DIR/mt5-forex-start.ini"

cat >"$PRESET" <<EOF
InpHubUrl=$MT5_HUB_URL
InpBridgeToken=$MT5_BRIDGE_TOKEN
InpAllowLiveTrading=$LIVE_BOOL
InpPulseSeconds=60
InpMaxRiskPct=0.50
InpMagic=560501
InpSymbols=$MT5_SYMBOLS
InpBreakEvenR=1.00
InpProfitLockR=1.35
InpTrailR=1.60
EOF
chmod 0600 "$PRESET"

{
  echo '[Common]'
  [[ -n "$MT5_ACCOUNT_LOGIN" ]] && echo "Login=$MT5_ACCOUNT_LOGIN"
  [[ -n "$MT5_ACCOUNT_PASSWORD" ]] && echo "Password=$MT5_ACCOUNT_PASSWORD"
  [[ -n "$MT5_ACCOUNT_SERVER" ]] && echo "Server=$MT5_ACCOUNT_SERVER"
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
} >"$CONFIG"
chmod 0600 "$CONFIG"

if [[ "$LIVE_BOOL" == true ]]; then
  if [[ -z "$MT5_ACCOUNT_LOGIN" || -z "$MT5_ACCOUNT_PASSWORD" || -z "$MT5_ACCOUNT_SERVER" ]]; then
    echo "ERROR: LIVE requested but broker credentials are incomplete" >&2
    exit 11
  fi
  if [[ -z "$MT5_BRIDGE_TOKEN" || -z "$MT5_HUB_URL" ]]; then
    echo "ERROR: LIVE requested but MT5 bridge configuration is incomplete" >&2
    exit 12
  fi
fi

WINEPATH_BIN="$(command -v winepath || true)"
CONFIG_WIN=""
if [[ -n "$WINEPATH_BIN" ]]; then
  CONFIG_WIN="$(HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" "$WINEPATH_BIN" -w "$CONFIG" 2>/dev/null || true)"
fi
if [[ -z "$CONFIG_WIN" ]]; then
  CONFIG_WIN='C:\MT5Forex\mt5-forex-start.ini'
fi

# Deliberately do not print account number, password, broker server or bridge token.
echo "MT5_FOREX_START=PASS"
echo "MT5_FOREX_RUNTIME_SCOPE=VPS_ONLY"
echo "MT5_FOREX_HOST_AUTHORIZED=PASS"
echo "MT5_FOREX_MODE=$([[ "$LIVE_BOOL" == true ]] && echo LIVE || echo PAPER)"
echo "MT5_FOREX_CREDENTIALS=$([[ -n "$MT5_ACCOUNT_LOGIN" && -n "$MT5_ACCOUNT_PASSWORD" && -n "$MT5_ACCOUNT_SERVER" ]] && echo CONFIGURED || echo INCOMPLETE)"

exec xvfb-run -a -s '-screen 0 1280x1024x24' env \
  HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" WINEARCH=win64 WINEDEBUG=-all \
  "$MT5_WINE_BIN" "$MT5_TERMINAL" /portable "/config:$CONFIG_WIN"
