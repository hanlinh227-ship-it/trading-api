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

[[ ${EUID} -eq 0 ]] || { echo "ERROR: run as root" >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo "ERROR: unsupported OS" >&2; exit 3; }
source /etc/os-release
case "${ID:-}" in ubuntu|debian|linuxmint) ;; *) echo "ERROR: unsupported distro" >&2; exit 4 ;; esac

wait_dpkg(){ local i; for i in $(seq 1 120); do if ! fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1; then return 0; fi; sleep 2; done; echo "ERROR: dpkg lock did not clear" >&2; return 1; }
apt_retry(){ local i rc=0; for i in $(seq 1 6); do wait_dpkg || true; set +e; "$@"; rc=$?; set -e; [[ $rc -eq 0 ]] && return 0; sleep $((i*3)); done; return "$rc"; }

export DEBIAN_FRONTEND=noninteractive
if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then dpkg --add-architecture i386 || true; fi
wait_dpkg
apt_retry apt-get update -y
apt_retry apt-get install -y --no-install-recommends ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc python3 fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils xz-utils

# MT5 build 6140 explicitly rejects the old Ubuntu Wine 9 runtime on this VPS.
# MetaQuotes' current Linux guidance recommends an up-to-date Wine environment.
# Pin to the current WineHQ stable major (11.x) and rebuild the prefix when the
# stack marker changes, so old Wine registry/runtime state cannot leak forward.
apt_retry apt-get purge -y wine wine64 wine32:i386 libwine:amd64 libwine:i386 winehq-staging wine-staging wine-staging-amd64 wine-staging-i386:i386 winehq-devel wine-devel wine-devel-amd64 wine-devel-i386:i386 || true
apt_retry apt-get -f install -y
install -d -m 0755 /etc/apt/keyrings
wget -qO- https://dl.winehq.org/wine-builds/winehq.key | gpg --dearmor --yes -o /etc/apt/keyrings/winehq-archive.key
chmod 0644 /etc/apt/keyrings/winehq-archive.key
if [[ "${VERSION_CODENAME:-}" == "noble" ]]; then
  wget -qO /etc/apt/sources.list.d/winehq-noble.sources https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources
elif [[ -n "${VERSION_CODENAME:-}" ]]; then
  wget -qO "/etc/apt/sources.list.d/winehq-${VERSION_CODENAME}.sources" "https://dl.winehq.org/wine-builds/ubuntu/dists/${VERSION_CODENAME}/winehq-${VERSION_CODENAME}.sources"
fi
apt_retry apt-get update -y
apt_retry apt-get install -y --install-recommends winehq-stable

WINE_BIN="/usr/bin/wine"
WINEBOOT_BIN="/usr/bin/wineboot"
WINEPATH_BIN="/usr/bin/winepath"
WINESERVER_BIN="/usr/bin/wineserver"
[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINEPATH_BIN" && -x "$WINESERVER_BIN" ]] || { echo "ERROR: WineHQ runtime incomplete" >&2; exit 5; }
WINE_VERSION_TEXT="$($WINE_BIN --version 2>/dev/null || true)"
WINE_MAJOR="$(printf '%s' "$WINE_VERSION_TEXT" | sed -nE 's/.*wine-([0-9]+).*/\1/p' | head -n1)"
[[ -n "$WINE_MAJOR" && "$WINE_MAJOR" -ge 11 ]] || { echo "ERROR: WineHQ 11+ required, got $WINE_VERSION_TEXT" >&2; exit 56; }
echo "MT5_WINE_STACK=$EXPECTED_STACK"
echo "MT5_WINE_VERSION=$WINE_VERSION_TEXT"
echo "MT5_WINE_STACK_CONSISTENCY=PASS"

if ! id -u "$APP_USER" >/dev/null 2>&1; then useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"; fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME" "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.local/share/applications" "$APP_HOME/.config" "$APP_HOME/.cache"
run_as_mt5(){ sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEDEBUG=-all "$@"; }
stop_mt5_wine(){ run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true; sleep 1; }

prefix_ready(){
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || return 1
  [[ -f "$STACK_MARKER" ]] || return 1
  [[ "$(cat "$STACK_MARKER" 2>/dev/null || true)" == "$EXPECTED_STACK" ]] || return 1
  find "$WINEPREFIX_DIR/drive_c/windows" -type f -iname kernel32.dll -print -quit 2>/dev/null | grep -q .
}
wine_smoke(){
  local rc=0
  stop_mt5_wine; set +e
  run_as_mt5 timeout 60 xvfb-run -a -s "$SCREEN" "$WINE_BIN" cmd /d /c "echo WINE_RUNTIME_OK" >/tmp/mt5-wine-smoke.log 2>&1
  rc=$?; set -e; stop_mt5_wine
  [[ $rc -eq 0 ]] && grep -q 'WINE_RUNTIME_OK' /tmp/mt5-wine-smoke.log
}
recreate_prefix(){
  local stamp rc=0; stamp="$(date +%Y%m%d%H%M%S)"; stop_mt5_wine
  if [[ -d "$WINEPREFIX_DIR" ]]; then mv "$WINEPREFIX_DIR" "${WINEPREFIX_DIR}.pre-wine11-${stamp}" || rm -rf "$WINEPREFIX_DIR"; fi
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$WINEPREFIX_DIR"
  set +e; run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" -i >/tmp/mt5-wineboot.log 2>&1; rc=$?; set -e; stop_mt5_wine
  echo "MT5_WINEBOOT_EXIT=$rc"
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || return 1
  printf '%s\n' "$EXPECTED_STACK" >"$STACK_MARKER"; chown "$APP_USER:$APP_USER" "$STACK_MARKER"; chmod 0600 "$STACK_MARKER"
}
if prefix_ready && wine_smoke; then echo "MT5_WINE_PREFIX_REPAIR=NOT_NEEDED"; else recreate_prefix || { echo "ERROR: WineHQ prefix rebuild failed" >&2; tail -200 /tmp/mt5-wineboot.log >&2 || true; exit 51; }; wine_smoke || { echo "ERROR: WineHQ runtime smoke failed" >&2; tail -160 /tmp/mt5-wine-smoke.log >&2 || true; exit 55; }; fi
echo "MT5_WINE_PREFIX=PASS"

wget -q --https-only -O "$INSTALLER" "$INSTALLER_URL"
chown "$APP_USER:$APP_USER" "$INSTALLER"; chmod 0640 "$INSTALLER"
echo "MT5_INSTALLER_SHA256=$(sha256sum "$INSTALLER" | awk '{print $1}')"
find_terminal(){
  local c found=""
  for c in "$INSTALL_ROOT/terminal64.exe" "$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5/terminal64.exe"; do [[ -f "$c" ]] && { printf '%s\n' "$c"; return 0; }; done
  found="$(find "$WINEPREFIX_DIR/drive_c" -maxdepth 8 -type f -iname terminal64.exe -print -quit 2>/dev/null || true)"; [[ -n "$found" ]] && printf '%s\n' "$found"
}
TERMINAL="$(find_terminal || true)"
if [[ -z "$TERMINAL" ]]; then
  stop_mt5_wine; set +e
  run_as_mt5 timeout 900 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$INSTALLER" /auto /path:'C:\MT5Forex' >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?; set -e; stop_mt5_wine; echo "MT5_INSTALLER_EXIT=$INSTALL_RC"; TERMINAL="$(find_terminal || true)"
fi
[[ -n "$TERMINAL" && -f "$TERMINAL" ]] || { echo "ERROR: MT5 terminal64.exe not found after installer" >&2; tail -240 /tmp/mt5-install.log >&2 || true; exit 6; }
MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/MQL5/Files/FOREX_BRIDGE" "$MT5_DIR/Config"

[[ -f "$EA_SRC" ]] || { echo "ERROR: canonical EA source missing: $EA_SRC" >&2; exit 7; }
EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"; EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"
SRC_SHA="$(sha256sum "$EA_SRC" | awk '{print $1}')"; DST_SHA="$(sha256sum "$EA_DST" | awk '{print $1}')"
[[ "$SRC_SHA" = "$DST_SHA" ]] || { echo "ERROR: EA source sync mismatch" >&2; exit 71; }
echo "MT5_EA_SOURCE_SHA256=$SRC_SHA"
grep -q "#property version   \"${EXPECTED_EA_VERSION}\"" "$EA_DST" || { echo "ERROR: expected EA version ${EXPECTED_EA_VERSION} not present" >&2; exit 72; }
METAEDITOR=""; for c in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do [[ -f "$c" ]] && { METAEDITOR="$c"; break; }; done
[[ -n "$METAEDITOR" ]] || { echo "ERROR: MetaEditor not found" >&2; exit 8; }

EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || true)"; LOG_HOST="$MT5_DIR/metaeditor-compile.log"; LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$LOG_HOST" 2>/dev/null || true)"
[[ -n "$EA_WIN" && -n "$LOG_WIN" ]] || { echo "ERROR: winepath failed for EA compile" >&2; exit 73; }
rm -f "$EA_EX5" "$LOG_HOST" /tmp/mt5-compile.log
stop_mt5_wine; set +e
run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1
COMPILE_RC=$?; set -e; stop_mt5_wine; echo "MT5_METAEDITOR_EXIT=$COMPILE_RC"
if [[ ! -f "$EA_EX5" ]]; then echo "ERROR: ForexAutoThe5ers.ex5 was not produced" >&2; [[ -f "$LOG_HOST" ]] && { iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST"; } | tail -200 >&2 || true; tail -160 /tmp/mt5-compile.log >&2 || true; exit 9; fi
if [[ -f "$LOG_HOST" ]]; then LOG_TEXT="$(iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST")"; printf '%s' "$LOG_TEXT" | grep -Eq 'Result:[[:space:]]+0 errors' || { echo "ERROR: MetaEditor log did not confirm 0 errors" >&2; printf '%s\n' "$LOG_TEXT" | tail -160 >&2; exit 74; }; fi

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

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_TERMINAL=$TERMINAL"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_BINARY=$EA_EX5"
echo "MT5_FOREX_EA_COMPILE=PASS"
echo "MT5_FOREX_LOCAL_BRIDGE_DIR=PASS"
