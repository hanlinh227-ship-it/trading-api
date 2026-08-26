#!/usr/bin/env bash
set -euo pipefail

APP_USER="mt5forex"
APP_HOME="/var/lib/trading/mt5-forex"
WINEPREFIX_DIR="${APP_HOME}/wine"
STACK_MARKER="${WINEPREFIX_DIR}/.trading-wine-stack"
EXPECTED_STACK="UBUNTU_DISTRO_WINE"
INSTALL_ROOT="${WINEPREFIX_DIR}/drive_c/MT5Forex"
REPO="${FOREX_RESEARCH_REPO:-/opt/trading/trading-api-main}"
EA_SRC="${REPO}/mt5/ForexAutoThe5ers.mq5"
INSTALLER_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
INSTALLER="${APP_HOME}/mt5setup.exe"
SCREEN="-screen 0 1280x1024x24"

[[ ${EUID} -eq 0 ]] || { echo "ERROR: run as root" >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo "ERROR: unsupported OS" >&2; exit 3; }
# shellcheck disable=SC1091
source /etc/os-release
case "${ID:-}" in ubuntu|debian|linuxmint) ;; *) echo "ERROR: unsupported distro" >&2; exit 4 ;; esac

export DEBIAN_FRONTEND=noninteractive
if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then
  dpkg --add-architecture i386 || true
fi

apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc \
  fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils

# MT5 on this Ubuntu 24.04 VPS fails before process startup with WineHQ 11 even
# after a clean prefix. Use one self-consistent Ubuntu Wine stack instead. The
# original c0000135 incident was caused by mixing WineHQ executables with distro
# libwine, not by the distro stack itself.
apt-get purge -y \
  winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386 \
  winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 \
  winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386 2>/dev/null || true
apt-get -f install -y
apt-get install -y --install-recommends \
  wine wine64 wine32:i386 libwine:amd64 libwine:i386

WINE_BIN="/usr/bin/wine"
WINEBOOT_BIN="/usr/bin/wineboot"
WINEPATH_BIN="/usr/bin/winepath"
WINESERVER_BIN="/usr/bin/wineserver"
[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINESERVER_BIN" ]] || {
  echo "ERROR: complete Ubuntu Wine runtime not found" >&2
  exit 5
}

# Fail if any WineHQ runtime package survived and could contaminate loaders/DLLs.
for pkg in \
  winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386 \
  winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 \
  winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386; do
  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
    echo "ERROR: WineHQ package still installed: $pkg" >&2
    exit 53
  fi
done

for pkg in wine wine64 wine32:i386 libwine:amd64 libwine:i386; do
  dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' || {
    echo "ERROR: required Ubuntu Wine package missing: $pkg" >&2
    exit 54
  }
done

echo "MT5_WINE_STACK=$EXPECTED_STACK"
echo "MT5_WINE_BIN=$WINE_BIN"
echo "MT5_WINE_VERSION=$($WINE_BIN --version 2>/dev/null || echo UNKNOWN)"
echo "MT5_WINE_STACK_CONSISTENCY=PASS"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.local/share/applications" \
  "$APP_HOME/.config" "$APP_HOME/.cache"

# Do not force WINEARCH. Ubuntu Wine on amd64 will create its native default
# prefix; forcing an architecture across different Wine families can make an old
# prefix unusable. All Wine calls use only HOME + WINEPREFIX.
run_as_mt5() {
  sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all "$@"
}

stop_mt5_wine() {
  run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true
  sleep 1
}

prefix_artifacts_ready() {
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || return 1
  [[ -f "$STACK_MARKER" ]] || return 1
  [[ "$(cat "$STACK_MARKER" 2>/dev/null || true)" == "$EXPECTED_STACK" ]] || return 1
  find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .
}

wine_runtime_smoke() {
  local rc=0
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 45 xvfb-run -a -s "$SCREEN" "$WINE_BIN" cmd /d /c "echo WINE_RUNTIME_OK" >/tmp/mt5-wine-smoke.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  if [[ $rc -eq 0 ]] && grep -q 'WINE_RUNTIME_OK' /tmp/mt5-wine-smoke.log; then
    echo "MT5_WINE_RUNTIME_SMOKE=PASS"
    return 0
  fi
  echo "MT5_WINE_RUNTIME_SMOKE=FAIL rc=$rc" >&2
  tail -160 /tmp/mt5-wine-smoke.log >&2 || true
  return 1
}

recreate_prefix() {
  local stamp rc=0
  stamp="$(date +%Y%m%d%H%M%S)"
  stop_mt5_wine
  if [[ -d "$WINEPREFIX_DIR" ]]; then
    mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.broken-${stamp}" || rm -rf "$WINEPREFIX_DIR"
  fi
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  echo "MT5_WINE_PREFIX_REPAIR=RECREATE"
  set +e
  run_as_mt5 timeout 120 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" -i >/tmp/mt5-wineboot.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  echo "MT5_WINEBOOT_EXIT=$rc"
  if [[ -f "$WINEPREFIX_DIR/system.reg" ]] && \
     find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .; then
    printf '%s\n' "$EXPECTED_STACK" > "$STACK_MARKER"
    chown "$APP_USER:$APP_USER" "$STACK_MARKER"
    chmod 0600 "$STACK_MARKER"
    return 0
  fi
  return 1
}

# Stack change is an unconditional prefix boundary. Never reuse a prefix created
# by WineHQ 11/staging under Ubuntu Wine 9.
if prefix_artifacts_ready && wine_runtime_smoke; then
  echo "MT5_WINE_PREFIX_REPAIR=NOT_NEEDED"
else
  recreate_prefix || {
    echo "ERROR: Ubuntu Wine prefix artifacts missing after rebuild" >&2
    tail -200 /tmp/mt5-wineboot.log >&2 || true
    exit 51
  }
  wine_runtime_smoke || {
    echo "ERROR: Ubuntu Wine cannot execute cmd.exe after clean rebuild" >&2
    exit 55
  }
fi

echo "MT5_WINE_PREFIX=PASS"

wget -q --https-only --show-progress -O "$INSTALLER" "$INSTALLER_URL"
chown "$APP_USER:$APP_USER" "$INSTALLER"
chmod 0640 "$INSTALLER"
echo "MT5_INSTALLER_SHA256=$(sha256sum "$INSTALLER" | awk '{print $1}')"

find_terminal() {
  local found=""
  for candidate in \
    "$INSTALL_ROOT/terminal64.exe" \
    "$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"; do
    [[ -f "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
  done
  found="$(find "$WINEPREFIX_DIR/drive_c" -maxdepth 7 -type f -iname terminal64.exe -print -quit 2>/dev/null || true)"
  [[ -n "$found" ]] && printf '%s\n' "$found"
}

TERMINAL="$(find_terminal || true)"
if [[ -z "$TERMINAL" ]]; then
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 900 xvfb-run -a -s "$SCREEN" \
    "$WINE_BIN" "$INSTALLER" /auto /path:'C:\MT5Forex' >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?
  set -e
  stop_mt5_wine
  echo "MT5_INSTALLER_EXIT=$INSTALL_RC"
  TERMINAL="$(find_terminal || true)"
fi

if [[ -z "$TERMINAL" || ! -f "$TERMINAL" ]]; then
  echo "ERROR: MT5 terminal64.exe not found after installer" >&2
  tail -240 /tmp/mt5-install.log >&2 || true
  exit 6
fi

MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/Config"
echo "MT5_FOREX_TERMINAL=$TERMINAL"

EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"
[[ -f "$EA_SRC" ]] || { echo "ERROR: canonical EA source missing" >&2; exit 7; }
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"

METAEDITOR=""
for candidate in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do
  [[ -f "$candidate" ]] && { METAEDITOR="$candidate"; break; }
done
[[ -n "$METAEDITOR" ]] || { echo "ERROR: MetaEditor not found" >&2; exit 8; }

EA_WIN='C:\MT5Forex\MQL5\Experts\ForexAutoThe5ers.mq5'
LOG_WIN='C:\MT5Forex\metaeditor-compile.log'
if [[ -x "$WINEPATH_BIN" ]]; then
  EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || echo "$EA_WIN")"
  LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$MT5_DIR/metaeditor-compile.log" 2>/dev/null || echo "$LOG_WIN")"
fi

EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
rm -f "$EA_EX5"
stop_mt5_wine
set +e
run_as_mt5 timeout 180 xvfb-run -a -s "$SCREEN" \
  "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1
COMPILE_RC=$?
set -e
stop_mt5_wine
echo "MT5_METAEDITOR_EXIT=$COMPILE_RC"

if [[ ! -f "$EA_EX5" ]]; then
  echo "ERROR: ForexAutoThe5ers.ex5 was not produced" >&2
  tail -200 "$MT5_DIR/metaeditor-compile.log" >&2 2>/dev/null || true
  tail -200 /tmp/mt5-compile.log >&2 || true
  exit 9
fi

cat >"$APP_HOME/runtime.env" <<EOF
MT5_WINEPREFIX=$WINEPREFIX_DIR
MT5_TERMINAL=$TERMINAL
MT5_INSTALL_DIR=$MT5_DIR
MT5_WINE_BIN=$WINE_BIN
MT5_WINE_STACK=$EXPECTED_STACK
EOF
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"
chmod 0640 "$APP_HOME/runtime.env"

mkdir -p /opt/trading
ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_COMPILE=PASS"
