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

# Server bootstrap preference (fix 2026-08-27): MT5's [Common] Server= field
# resolves a broker SERVER NAME (via Config/servers.dat or MetaQuotes
# discovery). A raw host:port endpoint is not reliably accepted there and can
# leave the terminal silently unconnected while the EA still runs.
# Default is now DISPLAY-NAME-first; set MT5_SERVER_BOOTSTRAP_PREFER=endpoint
# to restore the previous endpoint-first behavior if the display name cannot
# resolve in this environment.
MT5_SERVER_BOOTSTRAP_PREFER="${MT5_SERVER_BOOTSTRAP_PREFER:-display}"
if [[ "${MT5_SERVER_BOOTSTRAP_PREFER,,}" == "endpoint" && -n "$MT5_ACCOUNT_ENDPOINT" ]]; then
  SERVER_BOOTSTRAP="$MT5_ACCOUNT_ENDPOINT"
else
  SERVER_BOOTSTRAP="${MT5_ACCOUNT_SERVER:-$MT5_ACCOUNT_ENDPOINT}"
fi

# Broker-aware server cache repair (fix 2026-08-27, round 2).
# Production evidence: Server=FivePercentOnline-Real, servers.dat has NO
# FivePercent entry, and the terminal journal shows NEITHER "authorized on"
# NOR "authorization failed" — MT5 cannot resolve the display name locally,
# network discovery did not supply it, so it has no endpoint to dial and
# NEVER STARTS authorization (silent). Repair order:
#   1. If the current servers.dat lacks the broker but a prefix backup HAS it,
#      restore the backup copy (current file is renamed .pre-restore-<ts>,
#      never deleted). Also restore matching broker .srv files if absent.
#   2. accounts.dat is restored only when currently missing/empty.
#   3. If after repair servers.dat STILL lacks the broker and
#      MT5_ACCOUNT_ENDPOINT is set, fall back to the endpoint automatically —
#      a direct access-point address does not need local name resolution.
# No credentials are read, printed, or modified.
BROKER_TOKEN="${SERVER_BOOTSTRAP%%-*}"
[[ -n "$BROKER_TOKEN" ]] || BROKER_TOKEN="$SERVER_BOOTSTRAP"
has_broker_string() { [[ -s "$1" ]] && { strings -el "$1" 2>/dev/null; strings "$1" 2>/dev/null; } | grep -qiF -- "$BROKER_TOKEN"; }

CUR_SERVERS="$MT5_INSTALL_DIR/Config/servers.dat"
if [[ -n "$BROKER_TOKEN" ]] && ! has_broker_string "$CUR_SERVERS"; then
  RESTORED=""
  while IFS= read -r cand; do
    [[ -n "$cand" ]] || continue
    if has_broker_string "$cand"; then
      ts="$(date +%Y%m%d%H%M%S)"
      [[ -f "$CUR_SERVERS" ]] && mv "$CUR_SERVERS" "${CUR_SERVERS}.pre-restore-${ts}"
      install -o mt5forex -g mt5forex -m 0640 "$cand" "$CUR_SERVERS"
      echo "MT5_FOREX_SERVERS_DAT_RESTORED_FROM=${cand%/*}"
      RESTORED=1
      break
    fi
  done < <(find "$APP_HOME" -type f -path "*/Config/servers.dat" ! -path "$MT5_WINEPREFIX/drive_c/MT5Forex/*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | cut -d' ' -f2-)
  [[ -n "$RESTORED" ]] || echo "MT5_FOREX_SERVERS_DAT_RESTORED_FROM=NO_BACKUP_WITH_BROKER"
fi
# Restore per-server .srv config files matching the broker if absent.
while IFS= read -r srv; do
  base="$(basename "$srv")"
  dst="$MT5_INSTALL_DIR/Config/$base"
  [[ -s "$dst" ]] || { install -o mt5forex -g mt5forex -m 0640 "$srv" "$dst" && echo "MT5_FOREX_SRV_RESTORED=$base"; }
done < <(find "$APP_HOME" -type f -path "*/Config/*.srv" ! -path "$MT5_WINEPREFIX/drive_c/MT5Forex/*" -iname "*${BROKER_TOKEN}*" 2>/dev/null | sort -u)

if has_broker_string "$CUR_SERVERS"; then
  echo "MT5_FOREX_SERVERS_DAT_HAS_BROKER=yes"
else
  echo "MT5_FOREX_SERVERS_DAT_HAS_BROKER=no"
  if [[ "${MT5_SERVER_BOOTSTRAP_PREFER,,}" != "display-only" && -n "$MT5_ACCOUNT_ENDPOINT" && "$SERVER_BOOTSTRAP" != "$MT5_ACCOUNT_ENDPOINT" ]]; then
    SERVER_BOOTSTRAP="$MT5_ACCOUNT_ENDPOINT"
    echo "MT5_FOREX_SERVER_BOOTSTRAP_AUTO=ENDPOINT_FALLBACK"
  fi
fi
case "$MT5_ACCOUNT_LOGIN" in
  ""|*[!0-9]*) echo "MT5_FOREX_BOOT_LOGIN_NUMERIC=no" ;;
  *) echo "MT5_FOREX_BOOT_LOGIN_NUMERIC=yes" ;;
esac
{
  echo '[Common]'
  [[ -n "$MT5_ACCOUNT_LOGIN" ]] && echo "Login=$MT5_ACCOUNT_LOGIN"
  [[ -n "$MT5_ACCOUNT_PASSWORD" ]] && echo "Password=$MT5_ACCOUNT_PASSWORD"
  [[ -n "$SERVER_BOOTSTRAP" ]] && echo "Server=$SERVER_BOOTSTRAP"
  echo 'ProxyEnable=0'
  # KeepPrivate=0 (fix 2026-08-27): KeepPrivate=1 tells MT5 NOT to store the
  # account password in the profile. With it, a PERSISTENT_SESSION launch
  # (no /config) can never re-authorize after restart -> connected=false
  # forever. 0 lets the terminal keep the encrypted session so restart
  # reconnects without credential re-injection.
  echo 'KeepPrivate=0'
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

# accounts.dat: restore only when currently missing/empty (may hold a prior
# authorized session). Never overwrite an existing one.
acct_dst="$MT5_INSTALL_DIR/Config/accounts.dat"
if [[ ! -s "$acct_dst" ]]; then
  acct_src="$(find "$APP_HOME" -type f -path "*/Config/accounts.dat" ! -path "$MT5_WINEPREFIX/drive_c/MT5Forex/*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
  if [[ -n "$acct_src" && -s "$acct_src" ]]; then
    install -o mt5forex -g mt5forex -m 0640 "$acct_src" "$acct_dst" && echo "MT5_FOREX_BROKER_CACHE_RESTORED=accounts.dat"
  else
    echo "MT5_FOREX_BROKER_CACHE_RESTORED=accounts.dat:NO_BACKUP_FOUND"
  fi
fi

# Wine 11 launch contract, verified on production 2026-08-27:
# - launch terminal directly with Wine; do not use `wine start /wait <unix path>`.
# - during early launch comm can equal terminal64.exe, but the stable Wine process
#   on this VPS reports comm=main while args contain C:\MT5Forex\terminal64.exe.
# - therefore detection must accept either representation while requiring the
#   process owner to be mt5forex and comm=main for args-based matching. This
#   avoids matching the monitor shell itself.
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
echo "MT5_FOREX_SERVER_BOOTSTRAP_SOURCE=$([[ "$SERVER_BOOTSTRAP" == "$MT5_ACCOUNT_ENDPOINT" && -n "$MT5_ACCOUNT_ENDPOINT" ]] && echo ENDPOINT || echo DISPLAY_NAME)"
echo "MT5_FOREX_SERVER_BOOTSTRAP_NAME=$SERVER_BOOTSTRAP"
echo "MT5_FOREX_WINE_VERSION=${MT5_WINE_VERSION:-UNKNOWN}"

TERM_BASENAME="$(basename "$MT5_TERMINAL")"
export APP_HOME MT5_WINEPREFIX MT5_WINE_BIN MT5_INSTALL_DIR LAUNCH_MODE TERM_BASENAME MT5_TERMINAL_APPEAR_TIMEOUT
printf -v CMD '%q ' "${LAUNCH_ARGS[@]}"
export CMD
exec xvfb-run -a -s '-screen 0 1280x1024x24' bash -c '
  set +e
  LOG="$APP_HOME/wine-terminal-launch.log"
  : > "$LOG"
  echo "MT5_FOREX_EXEC_MODE=$LAUNCH_MODE"
  HOME="$APP_HOME" WINEPREFIX="$MT5_WINEPREFIX" WINEDEBUG=-all "$MT5_WINE_BIN" $CMD >>"$LOG" 2>&1 &
  wine_pid=$!

  term_alive() {
    ps -u "$(id -u)" -o comm=,args= | awk -v base="$TERM_BASENAME" '\''
      $1==base {found=1}
      $1=="main" && $0 ~ /[\\\/]terminal64\.exe([[:space:]]|$)/ {found=1}
      END {exit found?0:1}
    '\''
  }
  dump_diag() {
    echo "MT5_FOREX_DIAG_PS_SNAPSHOT_BEGIN"
    ps -u "$(id -u)" -o comm=,args= | grep -vE "^(ps|grep|bash|xvfb|Xvfb|awk) " | head -30
    echo "MT5_FOREX_DIAG_PS_SNAPSHOT_END"
    echo "MT5_FOREX_DIAG_WINE_LOG_TAIL_BEGIN"
    tail -40 "$LOG" 2>/dev/null
    echo "MT5_FOREX_DIAG_WINE_LOG_TAIL_END"
  }
  # Broker auth evidence (fix 2026-08-27): decode the newest MT5 terminal
  # journal (UTF-16LE) and surface authorization/connection lines into the
  # service journal. Sanitized: 6+ digit numbers masked, password-bearing
  # lines never printed. Bounded to 25 lines per dump.
  auth_evidence() {
    local latest out
    latest=$(find "$MT5_INSTALL_DIR/logs" -maxdepth 1 -type f -iname "*.log" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -1 | cut -d" " -f2-)
    [[ -n "$latest" ]] || { echo "MT5_FOREX_AUTH_EVIDENCE=NO_TERMINAL_LOG"; return 0; }
    out=$(mktemp)
    iconv -f UTF-16LE -t UTF-8 "$latest" >"$out" 2>/dev/null || cp "$latest" "$out" 2>/dev/null
    echo "MT5_FOREX_AUTH_EVIDENCE_BEGIN source=$(basename "$latest")"
    matched=$(grep -aiE "authoriz|connect|network|account|server|login|scan|access point|trade server|resolve|srv|ping|dns|proxy|certificate" "$out" 2>/dev/null \
      | grep -aiv "password" \
      | tail -30 \
      | sed -E "s/[0-9]{6,}/[N]/g")
    if [[ -n "$matched" ]]; then
      printf "%s\n" "$matched"
    else
      # Silence itself is evidence: no auth was even attempted. Show the raw
      # tail so the next debugging round sees what the terminal DID log.
      echo "MT5_FOREX_AUTH_EVIDENCE=NO_AUTH_LINES_MATCHED"
      tail -15 "$out" 2>/dev/null | grep -aiv "password" | sed -E "s/[0-9]{6,}/[N]/g"
    fi
    echo "MT5_FOREX_AUTH_EVIDENCE_END"
    rm -f "$out"
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
  ( sleep 25; auth_evidence ) &
  while term_alive || kill -0 "$wine_pid" >/dev/null 2>&1; do sleep 5; done
  echo "MT5_FOREX_TERMINAL_EXITED=1"
  auth_evidence
  dump_diag
  exit 70
'
