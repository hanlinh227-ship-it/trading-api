#!/usr/bin/env bash
set -euo pipefail

APP_USER="mt5forex"
APP_HOME="/var/lib/trading/mt5-forex"
WINEPREFIX_DIR="${APP_HOME}/wine"
REPO="${FOREX_RESEARCH_REPO:-/opt/trading/trading-api-main}"
EA_SRC="${REPO}/mt5/ForexAutoThe5ers.mq5"
INSTALLER_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
INSTALLER="${APP_HOME}/mt5setup.exe"
SCREEN="-screen 0 1280x1024x24"

[[ ${EUID} -eq 0 ]] || { echo "ERROR: run as root" >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo "ERROR: unsupported OS" >&2; exit 3; }
source /etc/os-release
case "${ID:-}" in ubuntu|debian|linuxmint) ;; *) echo "ERROR: unsupported distro" >&2; exit 4 ;; esac

wait_dpkg(){
  local i
  for i in $(seq 1 90); do
    if ! fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  echo "ERROR: dpkg lock did not clear" >&2
  return 1
}
apt_retry(){
  local i rc=0
  for i in $(seq 1 6); do
    wait_dpkg || true
    set +e
    "$@"
    rc=$?
    set -e
    [[ $rc -eq 0 ]] && return 0
    sleep $((i*3))
  done
  return "$rc"
}

export DEBIAN_FRONTEND=noninteractive
if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then dpkg --add-architecture i386 || true; fi
wait_dpkg
apt_retry apt-get update -y
apt_retry apt-get install -y --no-install-recommends ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc python3 fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils xz-utils

CODENAME="${VERSION_CODENAME:-noble}"
install -d -m 0755 /etc/apt/keyrings
wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
wget -qO "/etc/apt/sources.list.d/winehq-${CODENAME}.sources" "https://dl.winehq.org/wine-builds/ubuntu/dists/${CODENAME}/winehq-${CODENAME}.sources"
apt_retry apt-get update -y
PINNED_WINEHQ_VERSION="${MT5_WINE_COMPAT_VERSION:-10.0.0.0~${CODENAME}-1}"
if apt-cache madison winehq-stable 2>/dev/null | awk '{print $3}' | grep -Fxq "$PINNED_WINEHQ_VERSION"; then
  WINEHQ_VERSION="$PINNED_WINEHQ_VERSION"
  echo "MT5_WINE_COMPAT_PIN=ACTIVE version=$WINEHQ_VERSION"
else
  WINEHQ_VERSION="$(apt-cache madison winehq-stable 2>/dev/null | awk '{print $3}' | awk '$0 ~ /^10\./ {print; exit}' || true)"
  if [[ -z "$WINEHQ_VERSION" ]]; then
    WINEHQ_VERSION="$(apt-cache madison winehq-stable 2>/dev/null | awk '{print $3}' | head -n1 || true)"
  fi
  echo "MT5_WINE_COMPAT_PIN=FALLBACK version=${WINEHQ_VERSION:-MISSING}"
fi
[[ -n "$WINEHQ_VERSION" ]] || { echo "ERROR: WineHQ stable unavailable" >&2; exit 56; }

INSTALLED_WINE="$(dpkg-query -W -f='${Version}' winehq-stable 2>/dev/null || true)"
if [[ "$INSTALLED_WINE" != "$WINEHQ_VERSION" ]]; then
  apt_retry apt-get install -y --allow-downgrades --install-recommends \
    "wine-stable-amd64=${WINEHQ_VERSION}" \
    "wine-stable-i386:i386=${WINEHQ_VERSION}" \
    "wine-stable=${WINEHQ_VERSION}" \
    "winehq-stable=${WINEHQ_VERSION}"
else
  echo "MT5_WINE_PACKAGES=ALREADY_READY version=$INSTALLED_WINE"
fi

WINE_BIN="/opt/wine-stable/bin/wine"
WINEBOOT_BIN="/opt/wine-stable/bin/wineboot"
WINEPATH_BIN="/opt/wine-stable/bin/winepath"
WINESERVER_BIN="/opt/wine-stable/bin/wineserver"
[[ -x "$WINE_BIN" && -x "$WINEBOOT_BIN" && -x "$WINEPATH_BIN" && -x "$WINESERVER_BIN" ]] || { echo "ERROR: Wine runtime incomplete" >&2; exit 5; }
WINE_VERSION_TEXT="$($WINE_BIN --version 2>/dev/null || true)"
WINE_MAJOR="$(printf '%s' "$WINE_VERSION_TEXT" | sed -nE 's/.*wine-([0-9]+).*/\1/p' | head -n1)"
[[ -n "$WINE_MAJOR" && "$WINE_MAJOR" -ge 10 ]] || { echo "ERROR: Wine >=10 required, got $WINE_VERSION_TEXT" >&2; exit 57; }
echo "MT5_WINE_VERSION=$WINE_VERSION_TEXT"

if ! id -u "$APP_USER" >/dev/null 2>&1; then useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"; fi
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$APP_HOME" "$APP_HOME/.local" "$APP_HOME/.local/share" "$APP_HOME/.config" "$APP_HOME/.cache" "$WINEPREFIX_DIR"

run_as_mt5(){ sudo -u "$APP_USER" env HOME="$APP_HOME" WINEPREFIX="$WINEPREFIX_DIR" WINEARCH=win64 WINEDEBUG=-all "$@"; }
stop_mt5_wine(){ run_as_mt5 "$WINESERVER_BIN" -k >/dev/null 2>&1 || true; sleep 1; }

if [[ ! -f "$WINEPREFIX_DIR/system.reg" ]]; then
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINEBOOT_BIN" --init >/tmp/mt5-wineboot.log 2>&1
  BOOT_RC=$?
  set -e
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || { echo "ERROR: Wine prefix init failed rc=$BOOT_RC" >&2; tail -160 /tmp/mt5-wineboot.log >&2 || true; exit 51; }
fi
echo "MT5_WINE_PREFIX=PASS"

find_terminal(){ find "$WINEPREFIX_DIR/drive_c" -maxdepth 9 -type f -iname terminal64.exe -print 2>/dev/null | head -n1 || true; }
recover_preserved_mt5(){
  local source_terminal source_dir target_dir
  source_terminal="$(find "$APP_HOME" -maxdepth 16 -type f -iname terminal64.exe ! -path "$WINEPREFIX_DIR/*" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "$source_terminal" ]] || return 1
  source_dir="$(dirname "$source_terminal")"
  [[ -f "$source_dir/metaeditor64.exe" || -f "$source_dir/MetaEditor64.exe" ]] || return 1
  target_dir="$WINEPREFIX_DIR/drive_c/Program Files/MetaTrader 5"
  rm -rf "$target_dir"
  install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$(dirname "$target_dir")"
  cp -a "$source_dir" "$target_dir"
  chown -R "$APP_USER:$APP_USER" "$target_dir"
  [[ -f "$target_dir/terminal64.exe" ]]
}

TERMINAL="$(find_terminal)"
if [[ -z "$TERMINAL" ]]; then recover_preserved_mt5 || true; TERMINAL="$(find_terminal)"; fi
if [[ -z "$TERMINAL" ]]; then
  wget -q --https-only -O "$INSTALLER" "$INSTALLER_URL"
  chown "$APP_USER:$APP_USER" "$INSTALLER"; chmod 0640 "$INSTALLER"
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 360 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$INSTALLER" /auto >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?
  set -e
  TERMINAL="$(find_terminal)"
  [[ -n "$TERMINAL" ]] || { echo "ERROR: MT5 installer failed rc=$INSTALL_RC" >&2; tail -200 /tmp/mt5-install.log >&2 || true; exit 6; }
fi

MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/MQL5/Files/FOREX_BRIDGE" "$MT5_DIR/Config"

[[ -f "$EA_SRC" ]] || { echo "ERROR: canonical EA source missing: $EA_SRC" >&2; exit 7; }
EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"
EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"
SRC_SHA="$(sha256sum "$EA_SRC" | awk '{print $1}')"; DST_SHA="$(sha256sum "$EA_DST" | awk '{print $1}')"
[[ "$SRC_SHA" = "$DST_SHA" ]] || { echo "ERROR: EA source sync mismatch" >&2; exit 71; }
echo "MT5_EA_SOURCE_SHA256=$SRC_SHA"
grep -q '#property version   "0.401"' "$EA_DST" || { echo "ERROR: expected EA version 0.401 not present" >&2; exit 72; }

METAEDITOR=""
for candidate in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do [[ -f "$candidate" ]] && { METAEDITOR="$candidate"; break; }; done
[[ -n "$METAEDITOR" ]] || { echo "ERROR: MetaEditor not found" >&2; exit 8; }

DOSDEV="$WINEPREFIX_DIR/dosdevices"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DOSDEV"
ln -sfn "$MT5_DIR" "$DOSDEV/t:"
chown -h "$APP_USER:$APP_USER" "$DOSDEV/t:" || true

wait_for_file(){ local f="$1" i; for i in $(seq 1 120); do [[ -s "$f" ]] && return 0; sleep 0.25; done; return 1; }
compile_metaeditor(){
  local src_name="$1" out="$2" log="$3" rc
  rm -f "$out" "$log" /tmp/mt5-compile.log
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$METAEDITOR" \
    "/compile:T:\\MQL5\\Experts\\${src_name}" \
    "/include:T:\\MQL5" /log >/tmp/mt5-compile.log 2>&1
  rc=$?
  set -e
  echo "MT5_METAEDITOR_EXIT=$rc source=$src_name"
  wait_for_file "$out" && return 0
  return 1
}

PROBE_SRC="$MT5_DIR/MQL5/Experts/CompileProbe.mq5"
PROBE_EX5="$MT5_DIR/MQL5/Experts/CompileProbe.ex5"
PROBE_LOG="$MT5_DIR/MQL5/Experts/CompileProbe.log"
cat >"$PROBE_SRC" <<'EOF'
#property strict
#property version "1.000"
int OnInit(){return(INIT_SUCCEEDED);}
void OnTick(){}
EOF
chown "$APP_USER:$APP_USER" "$PROBE_SRC"; chmod 0640 "$PROBE_SRC"
find "$WINEPREFIX_DIR" "$APP_HOME" -type f \( -iname 'CompileProbe.ex5' -o -iname 'ForexAutoThe5ers.ex5' \) -delete 2>/dev/null || true
if ! compile_metaeditor 'CompileProbe.mq5' "$PROBE_EX5" "$PROBE_LOG"; then
  echo "ERROR: MetaEditor compile probe did not produce EX5" >&2
  [[ -f "$PROBE_LOG" ]] && { iconv -f UTF-16LE -t UTF-8 "$PROBE_LOG" 2>/dev/null || cat "$PROBE_LOG"; } | tail -160 >&2 || true
  tail -160 /tmp/mt5-compile.log >&2 || true
  stop_mt5_wine
  exit 75
fi
echo "MT5_METAEDITOR_PROBE=PASS"
rm -f "$PROBE_SRC" "$PROBE_EX5" "$PROBE_LOG"

LOG_HOST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.log"
if ! compile_metaeditor 'ForexAutoThe5ers.mq5' "$EA_EX5" "$LOG_HOST"; then
  echo "ERROR: canonical ForexAutoThe5ers.ex5 was not produced" >&2
  [[ -f "$LOG_HOST" ]] && { iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST"; } | tail -200 >&2 || true
  tail -160 /tmp/mt5-compile.log >&2 || true
  find "$WINEPREFIX_DIR" "$APP_HOME" -type f \( -iname '*.ex5' -o -iname 'ForexAutoThe5ers.mq5' \) -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null | tail -160 >&2 || true
  stop_mt5_wine
  exit 9
fi

if [[ -f "$LOG_HOST" ]]; then
  LOG_TEXT="$(iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST")"
  printf '%s' "$LOG_TEXT" | grep -Eq 'Result:[[:space:]]+0 errors' || { echo "ERROR: MetaEditor log did not confirm 0 errors" >&2; printf '%s\n' "$LOG_TEXT" | tail -160 >&2; stop_mt5_wine; exit 74; }
fi
stop_mt5_wine

mkdir -p /opt/trading
ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal
{
  printf 'MT5_WINEPREFIX=%q\n' "$WINEPREFIX_DIR"
  printf 'MT5_TERMINAL=%q\n' "$TERMINAL"
  printf 'MT5_INSTALL_DIR=%q\n' "$MT5_DIR"
  printf 'MT5_WINE_BIN=%q\n' "$WINE_BIN"
  printf 'MT5_WINESERVER_BIN=%q\n' "$WINESERVER_BIN"
  printf 'MT5_WINEPATH_BIN=%q\n' "$WINEPATH_BIN"
  printf 'MT5_WINE_VERSION=%q\n' "$WINE_VERSION_TEXT"
} >"$APP_HOME/runtime.env"
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"; chmod 0640 "$APP_HOME/runtime.env"

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_TERMINAL=$TERMINAL"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_BINARY=$EA_EX5"
echo "MT5_FOREX_EA_COMPILE=PASS"
echo "MT5_FOREX_LOCAL_BRIDGE_DIR=PASS"