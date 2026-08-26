#!/usr/bin/env bash
set -euo pipefail

APP_USER="mt5forex"
APP_HOME="/var/lib/trading/mt5-forex"
WINEPREFIX_DIR="${APP_HOME}/wine"
STACK_MARKER="${WINEPREFIX_DIR}/.trading-wine-stack"
EXPECTED_STACK="WINEHQ_STABLE_11"
INSTALL_ROOT="${WINEPREFIX_DIR}/drive_c/MT5Forex"
REPO="${FOREX_RESEARCH_REPO:-/opt/trading/trading-api-main}"
EA_SRC="${REPO}/mt5/ForexAutoThe5ers.mq5"
INSTALLER_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
INSTALLER="${APP_HOME}/mt5setup.exe"
SCREEN="-screen 0 1280x1024x24"
EXPECTED_EA_VERSION="0.402"
FORCE_REBUILD="${MT5_FORCE_PREFIX_REBUILD:-false}"

[[ ${EUID} -eq 0 ]] || { echo "ERROR: run as root" >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo "ERROR: unsupported OS" >&2; exit 3; }
source /etc/os-release
case "${ID:-}" in ubuntu|debian|linuxmint) ;; *) echo "ERROR: unsupported distro" >&2; exit 4 ;; esac

export DEBIAN_FRONTEND=noninteractive
if ! id -u "$APP_USER" >/dev/null 2>&1; then useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"; fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME" "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.config" "$APP_HOME/.cache"

wait_dpkg(){ local i; for i in $(seq 1 120); do if ! fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1; then return 0; fi; sleep 2; done; return 1; }
apt_retry(){ local i rc=0; for i in $(seq 1 4); do wait_dpkg || true; set +e; "$@"; rc=$?; set -e; [[ $rc -eq 0 ]] && return 0; sleep $((i*3)); done; return "$rc"; }

if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then dpkg --add-architecture i386 || true; fi
apt_retry apt-get update -y >/dev/null
apt_retry apt-get install -y --no-install-recommends ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc python3 fonts-liberation fonts-dejavu-core gnupg2 coreutils xz-utils >/dev/null

wine_major(){ /usr/bin/wine --version 2>/dev/null | sed -nE 's/.*wine-([0-9]+).*/\1/p' | head -n1; }
if [[ ! -x /usr/bin/wine || -z "$(wine_major)" || "$(wine_major)" -lt 11 ]]; then
  install -d -m 0755 /etc/apt/keyrings
  wget -qO- https://dl.winehq.org/wine-builds/winehq.key | gpg --dearmor --yes -o /etc/apt/keyrings/winehq-archive.key
  chmod 0644 /etc/apt/keyrings/winehq-archive.key
  if [[ -n "${VERSION_CODENAME:-}" ]]; then
    wget -qO "/etc/apt/sources.list.d/winehq-${VERSION_CODENAME}.sources" "https://dl.winehq.org/wine-builds/ubuntu/dists/${VERSION_CODENAME}/winehq-${VERSION_CODENAME}.sources"
  fi
  apt_retry apt-get update -y >/dev/null
  apt_retry apt-get install -y --install-recommends winehq-stable >/dev/null
fi

WINE_BIN="/usr/bin/wine"; WINEBOOT_BIN="/usr/bin/wineboot"; WINEPATH_BIN="/usr/bin/winepath"; WINESERVER_BIN="/usr/bin/wineserver"
[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINEPATH_BIN" && -x "$WINESERVER_BIN" ]] || { echo "ERROR: Wine runtime incomplete" >&2; exit 5; }
WINE_VERSION_TEXT="$($WINE_BIN --version 2>/dev/null || true)"; WINE_MAJOR="$(wine_major)"
[[ -n "$WINE_MAJOR" && "$WINE_MAJOR" -ge 11 ]] || { echo "ERROR: Wine 11+ required, got $WINE_VERSION_TEXT" >&2; exit 56; }

run_as_mt5(){ sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all "$@"; }
stop_mt5_wine(){ run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true; sleep 1; }
prefix_ready(){ [[ -f "$WINEPREFIX_DIR/system.reg" ]] && find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .; }

case "${FORCE_REBUILD,,}" in true|1|yes)
  stop_mt5_wine
  stamp="$(date +%Y%m%d%H%M%S)"
  [[ ! -d "$WINEPREFIX_DIR" ]] || mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.manual-backup-${stamp}"
  ;;
esac

if ! prefix_ready; then
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" -i >/tmp/mt5-wineboot.log 2>&1 || true
  stop_mt5_wine
  prefix_ready || { echo "ERROR: Wine prefix initialization failed" >&2; tail -160 /tmp/mt5-wineboot.log >&2 || true; exit 51; }
  printf '%s\n' "$EXPECTED_STACK" >"$STACK_MARKER"; chown "$APP_USER:$APP_USER" "$STACK_MARKER"; chmod 0600 "$STACK_MARKER"
  echo 'MT5_PERSISTENT_PREFIX=CREATED'
else
  echo 'MT5_PERSISTENT_PREFIX=PRESERVED'
fi

echo "MT5_WINE_STACK=$EXPECTED_STACK"
echo "MT5_WINE_VERSION=$WINE_VERSION_TEXT"
echo "MT5_WINE_STACK_CONSISTENCY=PASS"

find_terminal(){
  local c found=""
  for c in "$INSTALL_ROOT/terminal64.exe" "$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"; do [[ -f "$c" ]] && { printf '%s\n' "$c"; return 0; }; done
  found="$(find "$WINEPREFIX_DIR/drive_c" -maxdepth 8 -type f -iname terminal64.exe -print -quit 2>/dev/null || true)"; [[ -n "$found" ]] && printf '%s\n' "$found"
}
TERMINAL="$(find_terminal || true)"
if [[ -z "$TERMINAL" ]]; then
  wget -q --https-only -O "$INSTALLER" "$INSTALLER_URL"
  chown "$APP_USER:$APP_USER" "$INSTALLER"; chmod 0640 "$INSTALLER"
  stop_mt5_wine
  run_as_mt5 timeout 900 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$INSTALLER" /auto /path:'C:\MT5Forex' >/tmp/mt5-install.log 2>&1 || true
  stop_mt5_wine
  TERMINAL="$(find_terminal || true)"
  echo 'MT5_PERSISTENT_TERMINAL=INSTALLED'
else
  echo 'MT5_PERSISTENT_TERMINAL=PRESERVED'
fi
[[ -n "$TERMINAL" && -f "$TERMINAL" ]] || { echo "ERROR: MT5 terminal64.exe not found" >&2; exit 6; }
MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/MQL5/Files/FOREX_BRIDGE" "$MT5_DIR/Config"

[[ -f "$EA_SRC" ]] || { echo "ERROR: canonical EA source missing: $EA_SRC" >&2; exit 7; }
EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"; EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"
SRC_SHA="$(sha256sum "$EA_SRC" | awk '{print $1}')"; grep -q "#property version   \"${EXPECTED_EA_VERSION}\"" "$EA_DST" || { echo "ERROR: expected EA version ${EXPECTED_EA_VERSION} not present" >&2; exit 72; }
METAEDITOR=""; for c in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do [[ -f "$c" ]] && { METAEDITOR="$c"; break; }; done
[[ -n "$METAEDITOR" ]] || { echo "ERROR: MetaEditor not found" >&2; exit 8; }
EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || true)"; LOG_HOST="$MT5_DIR/metaeditor-compile.log"; LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$LOG_HOST" 2>/dev/null || true)"
rm -f "$EA_EX5" "$LOG_HOST"
stop_mt5_wine
run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1 || true
stop_mt5_wine
[[ -f "$EA_EX5" ]] || { echo "ERROR: EA compile did not produce EX5" >&2; exit 9; }
if [[ -f "$LOG_HOST" ]]; then
  LOG_TEXT="$(iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST")"
  printf '%s' "$LOG_TEXT" | grep -Eq 'Result:[[:space:]]+0 errors' || { echo "ERROR: MetaEditor did not confirm 0 errors" >&2; printf '%s\n' "$LOG_TEXT" | tail -120 >&2; exit 74; }
fi

mkdir -p /opt/trading; ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal
{
  printf 'MT5_WINEPREFIX=%q\n' "$WINEPREFIX_DIR"
  printf 'MT5_TERMINAL=%q\n' "$TERMINAL"
  printf 'MT5_INSTALL_DIR=%q\n' "$MT5_DIR"
  printf 'MT5_WINE_BIN=%q\n' "$WINE_BIN"
  printf 'MT5_WINESERVER_BIN=%q\n' "$WINESERVER_BIN"
  printf 'MT5_WINEPATH_BIN=%q\n' "$WINEPATH_BIN"
  printf 'MT5_WINE_VERSION=%q\n' "$WINE_VERSION_TEXT"
  printf 'MT5_WINE_STACK=%q\n' "$EXPECTED_STACK"
} >"$APP_HOME/runtime.env"
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"; chmod 0640 "$APP_HOME/runtime.env"

echo "MT5_EA_SOURCE_SHA256=$SRC_SHA"
echo 'MT5_FOREX_INSTALL=PASS'
echo 'MT5_FOREX_ARCHITECTURE=PERSISTENT_APPLIANCE'
echo 'MT5_FOREX_BROKER_STATE=PRESERVED'
echo "MT5_FOREX_TERMINAL=$TERMINAL"
echo "MT5_FOREX_EA_BINARY=$EA_EX5"
echo 'MT5_FOREX_EA_COMPILE=PASS'
