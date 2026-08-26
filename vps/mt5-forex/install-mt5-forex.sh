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
MONO_VERSION="10.4.1"
GECKO_VERSION="2.47.4"

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
  ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc python3 \
  fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils xz-utils

# Use the newest coherent WineHQ stable runtime. Wine 11 has already passed the
# VPS wineboot/cmd smoke tests. The MT5 bootstrapper is handled separately below
# by recovering a preserved MetaQuotes installation before attempting setup.
CODENAME="${VERSION_CODENAME:-noble}"
install -d -m 0755 /etc/apt/keyrings
wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
wget -qO "/etc/apt/sources.list.d/winehq-${CODENAME}.sources" \
  "https://dl.winehq.org/wine-builds/ubuntu/dists/${CODENAME}/winehq-${CODENAME}.sources"
apt-get update -y

WINEHQ_VERSION="${MT5_WINE_COMPAT_VERSION:-$(apt-cache madison winehq-stable 2>/dev/null | awk '{print $3}' | head -n1 || true)}"
if [[ -z "$WINEHQ_VERSION" ]]; then
  echo "ERROR: WineHQ stable is not available for ${CODENAME}" >&2
  exit 56
fi
TARGET_MAJOR="$(printf '%s' "$WINEHQ_VERSION" | sed -nE 's/^([0-9]+).*/\1/p')"
if [[ -z "$TARGET_MAJOR" || "$TARGET_MAJOR" -lt 10 ]]; then
  echo "ERROR: WineHQ stable >=10 required, candidate=$WINEHQ_VERSION" >&2
  exit 57
fi
EXPECTED_STACK="WINEHQ_STABLE_${WINEHQ_VERSION}_MONO_${MONO_VERSION}_GECKO_${GECKO_VERSION}"
STACK_MARKER="${WINEPREFIX_DIR}/.trading-wine-stack"

for pkg in winehq-stable wine-stable wine-stable-amd64 'wine-stable-i386:i386'; do
  if ! apt-cache madison "$pkg" 2>/dev/null | awk '{print $3}' | grep -Fxq "$WINEHQ_VERSION"; then
    echo "ERROR: exact WineHQ package unavailable: $pkg=$WINEHQ_VERSION" >&2
    exit 59
  fi
done

echo "MT5_WINE_TARGET_VERSION=$WINEHQ_VERSION"

pkill -u "$APP_USER" -f 'terminal64.exe|MetaTrader|wineserver' 2>/dev/null || true
sleep 1
apt-mark unhold winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386 \
  winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 \
  winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386 2>/dev/null || true

dpkg --configure -a >/tmp/mt5-dpkg-configure.log 2>&1 || true
INSTALLED_STABLE="$(dpkg-query -W -f='${Version}' winehq-stable 2>/dev/null || true)"
STABLE_STATUS="$(dpkg-query -W -f='${Status}' winehq-stable 2>/dev/null || true)"
if [[ -n "$INSTALLED_STABLE" && ( "$INSTALLED_STABLE" != "$WINEHQ_VERSION" || "$STABLE_STATUS" != "install ok installed" ) ]]; then
  dpkg --remove --force-remove-reinstreq winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386 2>/dev/null || true
  dpkg --purge --force-all winehq-stable wine-stable wine-stable-amd64 wine-stable-i386:i386 2>/dev/null || true
fi

apt-get purge -y \
  wine wine64 wine32:i386 libwine:amd64 libwine:i386 \
  winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 \
  winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386 2>/dev/null || true
apt-get -f install -y
apt-get install -y --allow-downgrades --install-recommends \
  "wine-stable-amd64=${WINEHQ_VERSION}" \
  "wine-stable-i386:i386=${WINEHQ_VERSION}" \
  "wine-stable=${WINEHQ_VERSION}" \
  "winehq-stable=${WINEHQ_VERSION}"

WINE_BIN="/opt/wine-stable/bin/wine"
WINEBOOT_BIN="/opt/wine-stable/bin/wineboot"
WINEPATH_BIN="/opt/wine-stable/bin/winepath"
WINESERVER_BIN="/opt/wine-stable/bin/wineserver"
[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINEPATH_BIN" && -x "$WINESERVER_BIN" ]] || {
  echo "ERROR: complete WineHQ stable runtime not found" >&2
  exit 5
}

WINE_VERSION_TEXT="$($WINE_BIN --version 2>/dev/null || true)"
WINE_MAJOR="$(printf '%s' "$WINE_VERSION_TEXT" | sed -nE 's/.*wine-([0-9]+).*/\1/p' | head -n1)"
if [[ -z "$WINE_MAJOR" || "$WINE_MAJOR" -lt 10 ]]; then
  echo "ERROR: expected Wine >=10, got ${WINE_VERSION_TEXT:-UNKNOWN}" >&2
  exit 57
fi

for pkg in wine wine64 wine32:i386 libwine:amd64 libwine:i386 winehq-staging winehq-devel; do
  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
    echo "ERROR: conflicting Wine package still installed: $pkg" >&2
    exit 53
  fi
done

echo "MT5_WINE_STACK=$EXPECTED_STACK"
echo "MT5_WINE_BIN=$WINE_BIN"
echo "MT5_WINE_VERSION=$WINE_VERSION_TEXT"
echo "MT5_WINE_MAJOR=$WINE_MAJOR"
echo "MT5_WINE_STACK_CONSISTENCY=PASS"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.local/share/applications" \
  "$APP_HOME/.config" "$APP_HOME/.cache" "$APP_HOME/.cache/wine"

MONO_ROOT="/opt/wine-stable/share/wine/mono"
GECKO_ROOT="/opt/wine-stable/share/wine/gecko"
if [[ ! -d "$MONO_ROOT/wine-mono-${MONO_VERSION}" ]]; then
  mono_tmp="$(mktemp -d)"
  wget -q --https-only -O "$mono_tmp/mono.tar.xz" \
    "https://dl.winehq.org/wine/wine-mono/${MONO_VERSION}/wine-mono-${MONO_VERSION}-x86.tar.xz"
  mkdir -p "$MONO_ROOT"
  tar -xJf "$mono_tmp/mono.tar.xz" -C "$MONO_ROOT"
  rm -rf "$mono_tmp"
fi
if [[ ! -d "$GECKO_ROOT/wine-gecko-${GECKO_VERSION}-x86" ]]; then
  gecko32_tmp="$(mktemp -d)"
  wget -q --https-only -O "$gecko32_tmp/gecko.tar.xz" \
    "https://dl.winehq.org/wine/wine-gecko/${GECKO_VERSION}/wine-gecko-${GECKO_VERSION}-x86.tar.xz"
  mkdir -p "$GECKO_ROOT"
  tar -xJf "$gecko32_tmp/gecko.tar.xz" -C "$GECKO_ROOT"
  rm -rf "$gecko32_tmp"
fi
if [[ ! -d "$GECKO_ROOT/wine-gecko-${GECKO_VERSION}-x86_64" ]]; then
  gecko64_tmp="$(mktemp -d)"
  wget -q --https-only -O "$gecko64_tmp/gecko.tar.xz" \
    "https://dl.winehq.org/wine/wine-gecko/${GECKO_VERSION}/wine-gecko-${GECKO_VERSION}-x86_64.tar.xz"
  mkdir -p "$GECKO_ROOT"
  tar -xJf "$gecko64_tmp/gecko.tar.xz" -C "$GECKO_ROOT"
  rm -rf "$gecko64_tmp"
fi
[[ -d "$MONO_ROOT/wine-mono-${MONO_VERSION}" ]] || { echo "ERROR: Wine Mono shared runtime missing" >&2; exit 60; }
[[ -d "$GECKO_ROOT/wine-gecko-${GECKO_VERSION}-x86" ]] || { echo "ERROR: Wine Gecko x86 runtime missing" >&2; exit 61; }
[[ -d "$GECKO_ROOT/wine-gecko-${GECKO_VERSION}-x86_64" ]] || { echo "ERROR: Wine Gecko x86_64 runtime missing" >&2; exit 62; }
echo "MT5_WINE_MONO=PASS version=$MONO_VERSION"
echo "MT5_WINE_GECKO=PASS version=$GECKO_VERSION"

run_as_mt5() {
  sudo -u "$APP_USER" env \
    HOME="$APP_HOME" \
    WINEPREFIX="$WINEPREFIX_DIR" \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    "$@"
}

stop_mt5_wine() {
  run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true
  sleep 1
}

prefix_artifacts_ready() {
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || return 1
  [[ -f "$STACK_MARKER" ]] || return 1
  [[ "$(cat "$STACK_MARKER" 2>/dev/null || true)" == "$EXPECTED_STACK" ]] || return 1
  find "$WINEPREFIX_DIR/drive_c/windows/system32" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .
}

wine_runtime_smoke() {
  local rc=0
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 60 xvfb-run -a -s "$SCREEN" "$WINE_BIN" cmd /d /c "echo WINE_RUNTIME_OK" >/tmp/mt5-wine-smoke.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  if [[ $rc -eq 0 ]] && grep -q 'WINE_RUNTIME_OK' /tmp/mt5-wine-smoke.log; then
    echo "MT5_WINE_RUNTIME_SMOKE=PASS"
    return 0
  fi
  echo "MT5_WINE_RUNTIME_SMOKE=FAIL rc=$rc" >&2
  tail -200 /tmp/mt5-wine-smoke.log >&2 || true
  return 1
}

recreate_prefix() {
  local stamp rc=0
  stamp="$(date +%Y%m%d%H%M%S)"
  stop_mt5_wine
  if [[ -d "$WINEPREFIX_DIR" ]]; then
    mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.pre-wine-${stamp}" || rm -rf "$WINEPREFIX_DIR"
  fi
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  echo "MT5_WINE_PREFIX_REPAIR=RECREATE"
  set +e
  run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" --init >/tmp/mt5-wineboot.log 2>&1
  rc=$?
  set -e
  stop_mt5_wine
  echo "MT5_WINEBOOT_EXIT=$rc"
  if [[ $rc -ne 0 ]]; then
    echo "MT5_WINEBOOT_LOG_BEGIN"
    tail -200 /tmp/mt5-wineboot.log || true
    echo "MT5_WINEBOOT_LOG_END"
  fi
  if [[ -f "$WINEPREFIX_DIR/system.reg" ]] && \
     find "$WINEPREFIX_DIR/drive_c/windows/system32" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .; then
    printf '%s\n' "$EXPECTED_STACK" > "$STACK_MARKER"
    chown "$APP_USER:$APP_USER" "$STACK_MARKER"
    chmod 0600 "$STACK_MARKER"
    return 0
  fi
  return 1
}

if prefix_artifacts_ready && wine_runtime_smoke; then
  echo "MT5_WINE_PREFIX_REPAIR=NOT_NEEDED"
else
  recreate_prefix || {
    echo "ERROR: supported Wine prefix artifacts missing after rebuild" >&2
    tail -200 /tmp/mt5-wineboot.log >&2 || true
    exit 51
  }
  wine_runtime_smoke || {
    echo "ERROR: supported Wine cannot execute cmd.exe after clean rebuild" >&2
    tail -200 /tmp/mt5-wineboot.log >&2 || true
    exit 55
  }
fi

echo "MT5_WINE_PREFIX=PASS"
run_as_mt5 "$WINE_BIN" reg add 'HKCU\Software\Wine' /v Version /t REG_SZ /d win10 /f >/tmp/mt5-wine-winver.log 2>&1 || true

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

recover_preserved_mt5() {
  local source_terminal="" source_dir="" target_dir=""
  source_terminal="$(find "$APP_HOME" -maxdepth 14 -type f -iname terminal64.exe \
    ! -path "$WINEPREFIX_DIR/*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  if [[ -z "$source_terminal" ]]; then
    echo "MT5_PRESERVED_INSTALL=NOT_FOUND"
    return 1
  fi
  source_dir="$(dirname "$source_terminal")"
  if [[ ! -f "$source_dir/metaeditor64.exe" && ! -f "$source_dir/MetaEditor64.exe" ]]; then
    echo "MT5_PRESERVED_INSTALL=REJECT_NO_METAEDITOR source=$source_dir"
    return 1
  fi
  target_dir="$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5"
  rm -rf "$target_dir"
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$(dirname "$target_dir")"
  cp -a "$source_dir" "$target_dir"
  chown -R "$APP_USER:$APP_USER" "$target_dir"
  if [[ -f "$target_dir/terminal64.exe" ]]; then
    echo "MT5_PRESERVED_INSTALL=RECOVERED source=$source_dir"
    return 0
  fi
  return 1
}

TERMINAL="$(find_terminal || true)"
if [[ -z "$TERMINAL" ]]; then
  recover_preserved_mt5 || true
  TERMINAL="$(find_terminal || true)"
fi

if [[ -z "$TERMINAL" ]]; then
  wget -q --https-only --show-progress -O "$INSTALLER" "$INSTALLER_URL"
  chown "$APP_USER:$APP_USER" "$INSTALLER"
  chmod 0640 "$INSTALLER"
  echo "MT5_INSTALLER_SHA256=$(sha256sum "$INSTALLER" | awk '{print $1}')"
  stop_mt5_wine
  STANDARD_TERMINAL="$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"
  set +e
  run_as_mt5 timeout 360 xvfb-run -a -s "$SCREEN" bash -c '
    set +e
    wine_bin="$1"
    installer="$2"
    terminal="$3"
    "$wine_bin" "$installer" /auto >/tmp/mt5-installer-wine.log 2>&1 &
    installer_pid=$!
    for i in $(seq 1 150); do
      if [ -f "$terminal" ]; then
        sleep 12
        kill "$installer_pid" 2>/dev/null || true
        wait "$installer_pid" 2>/dev/null || true
        exit 0
      fi
      sleep 2
    done
    kill "$installer_pid" 2>/dev/null || true
    wait "$installer_pid" 2>/dev/null || true
    exit 124
  ' _ "$WINE_BIN" "$INSTALLER" "$STANDARD_TERMINAL" >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?
  set -e
  stop_mt5_wine
  echo "MT5_INSTALLER_EXIT=$INSTALL_RC"
  TERMINAL="$(find_terminal || true)"
fi

if [[ -z "$TERMINAL" || ! -f "$TERMINAL" ]]; then
  echo "ERROR: MT5 terminal64.exe not found after preserved-install recovery or installer" >&2
  echo "MT5_INSTALL_DIAGNOSTICS_BEGIN" >&2
  find "$APP_HOME" -maxdepth 14 -type f \( -iname terminal64.exe -o -iname metaeditor64.exe \) -print 2>/dev/null | tail -100 >&2 || true
  pgrep -a -f 'mt5setup|terminal64|wine|wineserver' >&2 || true
  find "$WINEPREFIX_DIR/drive_c" -maxdepth 7 -type f -mmin -10 -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null | tail -200 >&2 || true
  tail -240 /tmp/mt5-install.log >&2 || true
  tail -240 /tmp/mt5-installer-wine.log >&2 || true
  echo "MT5_INSTALL_DIAGNOSTICS_END" >&2
  exit 6
fi

MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 \
  "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/MQL5/Files/FOREX_BRIDGE" "$MT5_DIR/Config"
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
EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || echo "$EA_WIN")"
LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$MT5_DIR/metaeditor-compile.log" 2>/dev/null || echo "$LOG_WIN")"

EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
rm -f "$EA_EX5"
stop_mt5_wine
set +e
run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" \
  "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1
COMPILE_RC=$?
set -e
stop_mt5_wine
echo "MT5_METAEDITOR_EXIT=$COMPILE_RC"

if [[ ! -f "$EA_EX5" ]]; then
  echo "ERROR: ForexAutoThe5ers.ex5 was not produced" >&2
  tail -240 "$MT5_DIR/metaeditor-compile.log" >&2 2>/dev/null || true
  tail -240 /tmp/mt5-compile.log >&2 || true
  exit 9
fi

cat >"$APP_HOME/runtime.env" <<EOF
MT5_WINEPREFIX=$WINEPREFIX_DIR
MT5_TERMINAL=$TERMINAL
MT5_INSTALL_DIR=$MT5_DIR
MT5_WINE_BIN=$WINE_BIN
MT5_WINESERVER_BIN=$WINESERVER_BIN
MT5_WINEPATH_BIN=$WINEPATH_BIN
MT5_WINE_STACK=$EXPECTED_STACK
MT5_WINE_VERSION=$WINE_VERSION_TEXT
EOF
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"
chmod 0640 "$APP_HOME/runtime.env"

mkdir -p /opt/trading
ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_COMPILE=PASS"
echo "MT5_FOREX_LOCAL_BRIDGE_DIR=PASS"
