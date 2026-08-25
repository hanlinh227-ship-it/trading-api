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
  fonts-liberation fonts-dejavu-core gnupg2 software-properties-common

if ! command -v wine >/dev/null 2>&1 && ! command -v wine64 >/dev/null 2>&1; then
  apt-get install -y --no-install-recommends wine wine64 wine32 || \
    apt-get install -y --no-install-recommends wine64
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME" "$WINEPREFIX_DIR"

wget -q --https-only --show-progress -O "$INSTALLER" "$INSTALLER_URL"
chown "$APP_USER:$APP_USER" "$INSTALLER"
chmod 0640 "$INSTALLER"

echo "MT5_INSTALLER_SHA256=$(sha256sum "$INSTALLER" | awk '{print $1}')"

WINE_BIN="$(command -v wine64 || command -v wine || true)"
WINEBOOT_BIN="$(command -v wineboot || true)"
WINEPATH_BIN="$(command -v winepath || true)"
if [[ -z "$WINE_BIN" ]]; then
  echo "ERROR: wine executable not found" >&2
  exit 5
fi

if [[ -n "$WINEBOOT_BIN" ]]; then
  sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all \
    xvfb-run -a -s '-screen 0 1280x1024x24' "$WINEBOOT_BIN" -u >/tmp/mt5-wineboot.log 2>&1 || true
fi

# MetaQuotes documents /auto and /path for unattended installation.
sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all \
  xvfb-run -a -s '-screen 0 1280x1024x24' \
  "$WINE_BIN" "$INSTALLER" /auto /path:'C:\MT5Forex' >/tmp/mt5-install.log 2>&1 || true

TERMINAL=""
for candidate in \
  "$INSTALL_ROOT/terminal64.exe" \
  "$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"; do
  if [[ -f "$candidate" ]]; then TERMINAL="$candidate"; break; fi
done
if [[ -z "$TERMINAL" ]]; then
  TERMINAL="$(find "$WINEPREFIX_DIR/drive_c" -maxdepth 5 -type f -iname terminal64.exe -print -quit 2>/dev/null || true)"
fi
if [[ -z "$TERMINAL" || ! -f "$TERMINAL" ]]; then
  echo "ERROR: MT5 terminal64.exe not found after installer" >&2
  tail -120 /tmp/mt5-install.log >&2 || true
  exit 6
fi

MT5_DIR="$(dirname "$TERMINAL")"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/Config"

EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"
if [[ -f "$EA_SRC" ]]; then
  install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"
fi

METAEDITOR=""
for candidate in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do
  if [[ -f "$candidate" ]]; then METAEDITOR="$candidate"; break; fi
done
if [[ -n "$METAEDITOR" && -f "$EA_DST" ]]; then
  EA_WIN='C:\MT5Forex\MQL5\Experts\ForexAutoThe5ers.mq5'
  LOG_WIN='C:\MT5Forex\metaeditor-compile.log'
  if [[ -n "$WINEPATH_BIN" ]]; then
    EA_WIN="$(sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || echo "$EA_WIN")"
    LOG_WIN="$(sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" "$WINEPATH_BIN" -w "$MT5_DIR/metaeditor-compile.log" 2>/dev/null || echo "$LOG_WIN")"
  fi
  sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all \
    xvfb-run -a -s '-screen 0 1280x1024x24' \
    "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1 || true
fi

cat >"$APP_HOME/runtime.env" <<EOF
MT5_WINEPREFIX=$WINEPREFIX_DIR
MT5_TERMINAL=$TERMINAL
MT5_INSTALL_DIR=$MT5_DIR
MT5_WINE_BIN=$WINE_BIN
EOF
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"
chmod 0640 "$APP_HOME/runtime.env"

ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_TERMINAL=$TERMINAL"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
if [[ -f "$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5" ]]; then
  echo "MT5_FOREX_EA_COMPILE=PASS"
else
  echo "MT5_FOREX_EA_COMPILE=NOT_CONFIRMED"
  if [[ -f "$MT5_DIR/metaeditor-compile.log" ]]; then tail -80 "$MT5_DIR/metaeditor-compile.log" || true; fi
fi
