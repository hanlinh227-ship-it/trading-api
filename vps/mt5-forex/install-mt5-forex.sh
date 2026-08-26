#!/usr/bin/env bash
set -euo pipefail

APP_USER="mt5forex"
APP_HOME="/var/lib/trading/mt5-forex"
WINEPREFIX_DIR="${APP_HOME}/wine"
INSTALL_ROOT="${WINEPREFIX_DIR}/drive_c/MT5Forex"
REPO="${FOREX_RESEARCH_REPO:-/opt/trading/trading-api-main}"
EA_SRC="${REPO}/mt5/ForexAutoThe5ers.mq5"
INSTALLER_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
INSTALLER="${APP_HOME}/mt5setup.exe"
SCREEN="-screen 0 1280x1024x24"

if [[ ${EUID} -ne 0 ]]; then
  echo "ERROR: run as root" >&2
  exit 2
fi

if [[ ! -f /etc/os-release ]]; then
  echo "ERROR: unsupported OS (missing /etc/os-release)" >&2
  exit 3
fi
# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}" in
  ubuntu|debian|linuxmint) ;;
  *) echo "ERROR: unsupported Linux distro: ${ID:-unknown}" >&2; exit 4 ;;
esac

export DEBIAN_FRONTEND=noninteractive
if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then
  dpkg --add-architecture i386 || true
fi

apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc \
  fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils

# IMPORTANT: never mix WineHQ executables with Ubuntu libwine packages.
# The previous mixed Wine 11 wrapper + Ubuntu Wine 9 libraries caused c0000135.
WINE_STACK=""
if apt-cache policy winehq-stable 2>/dev/null | grep -Eq 'Candidate: [^()]'; then
  WINE_STACK="WINEHQ"

  # Purge distro Wine packages that can shadow/mix with WineHQ. WineHQ packages
  # use wine-stable* names and are reinstalled immediately below.
  apt-get remove -y \
    wine wine64 wine32:i386 libwine:amd64 libwine:i386 2>/dev/null || true
  apt-get -f install -y || true

  apt-get install -y --install-recommends --reinstall \
    winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386
else
  WINE_STACK="DISTRO"
  # Fallback only when WineHQ is unavailable. Do not install WineHQ in this path.
  if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then
    apt-get install -y --install-recommends wine wine64 wine32:i386
  else
    apt-get install -y --install-recommends wine
  fi
fi

echo "MT5_WINE_STACK=$WINE_STACK"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.local/share/applications" \
  "$APP_HOME/.config" "$APP_HOME/.cache"

WINE_BIN="$(command -v wine || true)"
WINEBOOT_BIN="$(command -v wineboot || true)"
WINEPATH_BIN="$(command -v winepath || true)"
if [[ -z "$WINE_BIN" || -z "$WINEBOOT_BIN" ]]; then
  echo "ERROR: complete Wine runtime not found" >&2
  exit 5
fi

WINE_VERSION="$($WINE_BIN --version 2>/dev/null || true)"
echo "MT5_WINE_VERSION=${WINE_VERSION:-UNKNOWN}"

# Detect a mixed installation before touching the prefix.
if [[ "$WINE_STACK" == "WINEHQ" ]]; then
  if dpkg-query -W -f='${Status}\n' libwine:amd64 2>/dev/null | grep -q 'install ok installed'; then
    echo "ERROR: Ubuntu libwine:amd64 still installed alongside WineHQ" >&2
    exit 53
  fi
  if dpkg-query -W -f='${Status}\n' libwine:i386 2>/dev/null | grep -q 'install ok installed'; then
    echo "ERROR: Ubuntu libwine:i386 still installed alongside WineHQ" >&2
    exit 54
  fi
fi

echo "MT5_WINE_STACK_CONSISTENCY=PASS"

run_as_mt5() {
  sudo -u "$APP_USER" env \
    HOME="$APP_HOME" \
    WINEPREFIX="$WINEPREFIX_DIR" \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    "$@"
}

wineboot_once() {
  run_as_mt5 timeout 120 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" -u >/tmp/mt5-wineboot.log 2>&1
}

find_terminal() {
  local found=""
  for candidate in \
    "$INSTALL_ROOT/terminal64.exe" \
    "$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  found="$(find "$WINEPREFIX_DIR/drive_c" -maxdepth 6 -type f -iname terminal64.exe -print -quit 2>/dev/null || true)"
  [[ -n "$found" ]] && printf '%s\n' "$found"
}

# Any prefix created by the previously mixed stack is untrusted. Preserve an
# already working MT5 installation only if wineboot succeeds; otherwise rebuild.
if [[ -d "$WINEPREFIX_DIR" ]]; then
  if ! wineboot_once; then
    stamp="$(date +%Y%m%d%H%M%S)"
    echo "MT5_WINE_PREFIX_REPAIR=RECREATE"
    mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.broken-${stamp}" || rm -rf "$WINEPREFIX_DIR"
    install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  else
    echo "MT5_WINE_PREFIX_REPAIR=NOT_NEEDED"
  fi
else
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
fi

# If the prefix is new/recreated, initialize it now.
if [[ ! -f "$WINEPREFIX_DIR/system.reg" ]]; then
  if ! wineboot_once; then
    echo "ERROR: Wine prefix initialization failed after clean rebuild" >&2
    tail -160 /tmp/mt5-wineboot.log >&2 || true
    exit 51
  fi
fi

KERNEL32="$(find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null || true)"
if [[ -z "$KERNEL32" ]]; then
  echo "ERROR: Wine prefix has no kernel32.dll after wineboot" >&2
  tail -160 /tmp/mt5-wineboot.log >&2 || true
  exit 52
fi
echo "MT5_WINE_PREFIX=PASS"

wget -q --https-only --show-progress -O "$INSTALLER" "$INSTALLER_URL"
chown "$APP_USER:$APP_USER" "$INSTALLER"
chmod 0640 "$INSTALLER"
echo "MT5_INSTALLER_SHA256=$(sha256sum "$INSTALLER" | awk '{print $1}')"

TERMINAL="$(find_terminal || true)"
if [[ -z "$TERMINAL" ]]; then
  set +e
  run_as_mt5 timeout 900 xvfb-run -a -s "$SCREEN" \
    "$WINE_BIN" "$INSTALLER" /auto /path:'C:\MT5Forex' >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?
  set -e
  echo "MT5_INSTALLER_EXIT=$INSTALL_RC"
  TERMINAL="$(find_terminal || true)"
fi

if [[ -z "$TERMINAL" || ! -f "$TERMINAL" ]]; then
  echo "ERROR: MT5 terminal64.exe not found after installer" >&2
  tail -200 /tmp/mt5-install.log >&2 || true
  exit 6
fi

MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/Config"

echo "MT5_FOREX_TERMINAL=$TERMINAL"

EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"
if [[ ! -f "$EA_SRC" ]]; then
  echo "ERROR: canonical EA source missing: $EA_SRC" >&2
  exit 7
fi
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"

METAEDITOR=""
for candidate in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do
  if [[ -f "$candidate" ]]; then METAEDITOR="$candidate"; break; fi
done
if [[ -z "$METAEDITOR" ]]; then
  echo "ERROR: MetaEditor not found; cannot compile canonical EA" >&2
  exit 8
fi

EA_WIN='C:\MT5Forex\MQL5\Experts\ForexAutoThe5ers.mq5'
LOG_WIN='C:\MT5Forex\metaeditor-compile.log'
if [[ -n "$WINEPATH_BIN" ]]; then
  EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || echo "$EA_WIN")"
  LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$MT5_DIR/metaeditor-compile.log" 2>/dev/null || echo "$LOG_WIN")"
fi

rm -f "$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
set +e
run_as_mt5 timeout 180 xvfb-run -a -s "$SCREEN" \
  "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1
COMPILE_RC=$?
set -e
echo "MT5_METAEDITOR_EXIT=$COMPILE_RC"

EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
if [[ ! -f "$EA_EX5" ]]; then
  echo "ERROR: ForexAutoThe5ers.ex5 was not produced" >&2
  tail -160 "$MT5_DIR/metaeditor-compile.log" >&2 2>/dev/null || true
  tail -160 /tmp/mt5-compile.log >&2 || true
  exit 9
fi

cat >"$APP_HOME/runtime.env" <<EOF
MT5_WINEPREFIX=$WINEPREFIX_DIR
MT5_TERMINAL=$TERMINAL
MT5_INSTALL_DIR=$MT5_DIR
MT5_WINE_BIN=$WINE_BIN
EOF
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"
chmod 0640 "$APP_HOME/runtime.env"

mkdir -p /opt/trading
ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_COMPILE=PASS"
