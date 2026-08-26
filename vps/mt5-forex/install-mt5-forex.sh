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

# One Wine family only. Purge distro Wine and WineHQ staging/devel packages so
# /usr/bin wrappers, loaders and DLLs can never come from different releases.
if apt-cache policy winehq-stable 2>/dev/null | grep -Eq 'Candidate: [^()]'; then
  apt-get remove -y \
    wine wine64 wine32:i386 libwine:amd64 libwine:i386 \
    winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 \
    winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386 2>/dev/null || true
  apt-get -f install -y || true
  apt-get install -y --install-recommends \
    winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386
  WINE_STACK="WINEHQ_STABLE"
else
  WINE_STACK="DISTRO"
  apt-get install -y --install-recommends wine wine64 wine32:i386
fi

echo "MT5_WINE_STACK=$WINE_STACK"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.local/share/applications" \
  "$APP_HOME/.config" "$APP_HOME/.cache"

if [[ "$WINE_STACK" == "WINEHQ_STABLE" && -x /opt/wine-stable/bin/wine ]]; then
  WINE_BIN=/opt/wine-stable/bin/wine
  WINEBOOT_BIN=/opt/wine-stable/bin/wineboot
  WINEPATH_BIN=/opt/wine-stable/bin/winepath
  WINESERVER_BIN=/opt/wine-stable/bin/wineserver
else
  WINE_BIN="$(command -v wine || true)"
  WINEBOOT_BIN="$(command -v wineboot || true)"
  WINEPATH_BIN="$(command -v winepath || true)"
  WINESERVER_BIN="$(command -v wineserver || true)"
fi

[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINESERVER_BIN" ]] || {
  echo "ERROR: complete Wine runtime not found" >&2; exit 5;
}

echo "MT5_WINE_BIN=$WINE_BIN"
echo "MT5_WINE_VERSION=$($WINE_BIN --version 2>/dev/null || echo UNKNOWN)"

if [[ "$WINE_STACK" == "WINEHQ_STABLE" ]]; then
  for pkg in libwine:amd64 libwine:i386 wine-staging wine-staging-amd64 wine-staging-i386:i386 winehq-staging; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
      echo "ERROR: conflicting Wine package remains: $pkg" >&2
      exit 53
    fi
  done
fi
echo "MT5_WINE_STACK_CONSISTENCY=PASS"

run_as_mt5() {
  sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEARCH=win64 WINEDEBUG=-all "$@"
}

stop_mt5_wine() {
  run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true
  sleep 1
}

prefix_artifacts_ready() {
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || return 1
  find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .
}

wine_runtime_smoke() {
  local rc=0
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 35 xvfb-run -a -s "$SCREEN" "$WINE_BIN" cmd /d /c "echo WINE_RUNTIME_OK" >/tmp/mt5-wine-smoke.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  if [[ $rc -eq 0 ]] && grep -q 'WINE_RUNTIME_OK' /tmp/mt5-wine-smoke.log; then
    echo "MT5_WINE_RUNTIME_SMOKE=PASS"
    return 0
  fi
  echo "MT5_WINE_RUNTIME_SMOKE=FAIL rc=$rc" >&2
  tail -120 /tmp/mt5-wine-smoke.log >&2 || true
  return 1
}

initialize_prefix() {
  local rc=0
  set +e
  run_as_mt5 timeout 75 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" -i >/tmp/mt5-wineboot.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  echo "MT5_WINEBOOT_EXIT=$rc"
  prefix_artifacts_ready
}

recreate_prefix() {
  local stamp
  stamp="$(date +%Y%m%d%H%M%S)"
  stop_mt5_wine
  if [[ -d "$WINEPREFIX_DIR" ]]; then
    mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.broken-${stamp}" || rm -rf "$WINEPREFIX_DIR"
  fi
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  echo "MT5_WINE_PREFIX_REPAIR=RECREATE"
  initialize_prefix || true
}

# A prefix is trusted only if it can execute a real Windows command. File
# existence alone is insufficient; previous bad prefixes contained kernel32.dll
# but still failed c0000135 at runtime.
if prefix_artifacts_ready && wine_runtime_smoke; then
  echo "MT5_WINE_PREFIX_REPAIR=NOT_NEEDED"
else
  recreate_prefix
  if ! prefix_artifacts_ready; then
    echo "ERROR: Wine prefix artifacts missing after rebuild" >&2
    tail -160 /tmp/mt5-wineboot.log >&2 || true
    exit 51
  fi
  if ! wine_runtime_smoke; then
    echo "ERROR: Wine cannot execute cmd.exe after clean rebuild" >&2
    exit 55
  fi
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
  tail -200 /tmp/mt5-install.log >&2 || true
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
if [[ -n "$WINEPATH_BIN" && -x "$WINEPATH_BIN" ]]; then
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
