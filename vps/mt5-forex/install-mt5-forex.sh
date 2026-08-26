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

export DEBIAN_FRONTEND=noninteractive
if [[ "$(dpkg --print-architecture)" == "amd64" ]]; then dpkg --add-architecture i386 || true; fi
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates wget curl xvfb xauth winbind cabextract unzip procps psmisc python3 fonts-liberation fonts-dejavu-core gnupg2 software-properties-common coreutils xz-utils

CODENAME="${VERSION_CODENAME:-noble}"
install -d -m 0755 /etc/apt/keyrings
wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
wget -qO "/etc/apt/sources.list.d/winehq-${CODENAME}.sources" "https://dl.winehq.org/wine-builds/ubuntu/dists/${CODENAME}/winehq-${CODENAME}.sources"
apt-get update -y
WINEHQ_VERSION="${MT5_WINE_COMPAT_VERSION:-$(apt-cache madison winehq-stable 2>/dev/null | awk '{print $3}' | head -n1 || true)}"
[[ -n "$WINEHQ_VERSION" ]] || { echo "ERROR: WineHQ stable unavailable" >&2; exit 56; }
apt-get install -y --allow-downgrades --install-recommends \
  "wine-stable-amd64=${WINEHQ_VERSION}" \
  "wine-stable-i386:i386=${WINEHQ_VERSION}" \
  "wine-stable=${WINEHQ_VERSION}" \
  "winehq-stable=${WINEHQ_VERSION}"

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
  stop_mt5_wine
  [[ -f "$WINEPREFIX_DIR/system.reg" ]] || { echo "ERROR: Wine prefix init failed rc=$BOOT_RC" >&2; tail -120 /tmp/mt5-wineboot.log >&2 || true; exit 51; }
fi

echo "MT5_WINE_PREFIX=PASS"

find_terminal(){
  find "$WINEPREFIX_DIR/drive_c" -maxdepth 8 -type f -iname terminal64.exe -print 2>/dev/null | head -n1 || true
}

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
  chown "$APP_USER:$APP_USER" "$INSTALLER"
  chmod 0640 "$INSTALLER"
  stop_mt5_wine
  set +e
  run_as_mt5 timeout 360 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$INSTALLER" /auto >/tmp/mt5-install.log 2>&1
  INSTALL_RC=$?
  set -e
  stop_mt5_wine
  TERMINAL="$(find_terminal)"
  [[ -n "$TERMINAL" ]] || { echo "ERROR: MT5 installer failed rc=$INSTALL_RC" >&2; tail -160 /tmp/mt5-install.log >&2 || true; exit 6; }
fi

MT5_DIR="$(dirname "$TERMINAL")"
chown -R "$APP_USER:$APP_USER" "$MT5_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$MT5_DIR/MQL5/Experts" "$MT5_DIR/MQL5/Presets" "$MT5_DIR/MQL5/Files/FOREX_BRIDGE" "$MT5_DIR/Config"

[[ -f "$EA_SRC" ]] || { echo "ERROR: canonical EA source missing: $EA_SRC" >&2; exit 7; }
EA_DST="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.mq5"
install -o "$APP_USER" -g "$APP_USER" -m 0640 "$EA_SRC" "$EA_DST"

# Canonical source verification: never compile an old fallback copy.
SRC_SHA="$(sha256sum "$EA_SRC" | awk '{print $1}')"
DST_SHA="$(sha256sum "$EA_DST" | awk '{print $1}')"
[[ "$SRC_SHA" = "$DST_SHA" ]] || { echo "ERROR: EA source sync mismatch" >&2; exit 71; }
echo "MT5_EA_SOURCE_SHA256=$SRC_SHA"
grep -q '#property version   "0.401"' "$EA_DST" || { echo "ERROR: expected EA version 0.401 not present" >&2; exit 72; }

METAEDITOR=""
for candidate in "$MT5_DIR/metaeditor64.exe" "$MT5_DIR/MetaEditor64.exe"; do [[ -f "$candidate" ]] && { METAEDITOR="$candidate"; break; }; done
[[ -n "$METAEDITOR" ]] || { echo "ERROR: MetaEditor not found" >&2; exit 8; }

EA_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$EA_DST" 2>/dev/null || true)"
LOG_HOST="$MT5_DIR/metaeditor-compile.log"
LOG_WIN="$(run_as_mt5 "$WINEPATH_BIN" -w "$LOG_HOST" 2>/dev/null || true)"
[[ -n "$EA_WIN" && -n "$LOG_WIN" ]] || { echo "ERROR: winepath failed; refusing stale C:\\MT5Forex fallback" >&2; exit 73; }
echo "MT5_EA_COMPILE_WINDOWS_PATH=$EA_WIN"

# Remove every old artifact before compile so a stale EX5 can never satisfy readiness.
find "$WINEPREFIX_DIR" "$APP_HOME" -type f -iname 'ForexAutoThe5ers.ex5' -delete 2>/dev/null || true
rm -f "$LOG_HOST" /tmp/mt5-compile.log
stop_mt5_wine
set +e
run_as_mt5 timeout 240 xvfb-run -a -s "$SCREEN" "$WINE_BIN" "$METAEDITOR" "/compile:$EA_WIN" "/log:$LOG_WIN" >/tmp/mt5-compile.log 2>&1
COMPILE_RC=$?
set -e
stop_mt5_wine
echo "MT5_METAEDITOR_EXIT=$COMPILE_RC"

# MetaEditor may place EX5 in the terminal data folder rather than beside the program binary.
FOUND_EX5="$(find "$WINEPREFIX_DIR" "$APP_HOME" -type f -iname 'ForexAutoThe5ers.ex5' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
EA_EX5="$MT5_DIR/MQL5/Experts/ForexAutoThe5ers.ex5"
if [[ -n "$FOUND_EX5" && -f "$FOUND_EX5" ]]; then
  if [[ "$FOUND_EX5" != "$EA_EX5" ]]; then install -o "$APP_USER" -g "$APP_USER" -m 0640 "$FOUND_EX5" "$EA_EX5"; fi
fi

if [[ ! -f "$EA_EX5" ]]; then
  echo "ERROR: canonical ForexAutoThe5ers.ex5 was not produced" >&2
  if [[ -f "$LOG_HOST" ]]; then iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null | tail -160 >&2 || tail -160 "$LOG_HOST" >&2 || true; fi
  tail -120 /tmp/mt5-compile.log >&2 || true
  echo "MT5_EX5_SEARCH_BEGIN" >&2
  find "$WINEPREFIX_DIR" "$APP_HOME" -type f \( -iname '*.ex5' -o -iname 'ForexAutoThe5ers.mq5' \) -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' 2>/dev/null | tail -120 >&2 || true
  echo "MT5_EX5_SEARCH_END" >&2
  exit 9
fi

# Require the compile log to prove zero compile errors when available.
if [[ -f "$LOG_HOST" ]]; then
  LOG_TEXT="$(iconv -f UTF-16LE -t UTF-8 "$LOG_HOST" 2>/dev/null || cat "$LOG_HOST")"
  printf '%s' "$LOG_TEXT" | grep -Eq 'Result:[[:space:]]+0 errors' || { echo "ERROR: MetaEditor log did not confirm 0 errors" >&2; printf '%s\n' "$LOG_TEXT" | tail -120 >&2; exit 74; }
fi

cat >"$APP_HOME/runtime.env" <<EOF
MT5_WINEPREFIX=$WINEPREFIX_DIR
MT5_TERMINAL=$TERMINAL
MT5_INSTALL_DIR=$MT5_DIR
MT5_WINE_BIN=$WINE_BIN
MT5_WINESERVER_BIN=$WINESERVER_BIN
MT5_WINEPATH_BIN=$WINEPATH_BIN
MT5_WINE_VERSION=$WINE_VERSION_TEXT
EOF
chown "$APP_USER:$APP_USER" "$APP_HOME/runtime.env"
chmod 0640 "$APP_HOME/runtime.env"
mkdir -p /opt/trading
ln -sfn "$MT5_DIR" /opt/trading/mt5-forex-terminal

echo "MT5_FOREX_INSTALL=PASS"
echo "MT5_FOREX_TERMINAL=$TERMINAL"
echo "MT5_FOREX_EA_SOURCE=$EA_DST"
echo "MT5_FOREX_EA_BINARY=$EA_EX5"
echo "MT5_FOREX_EA_COMPILE=PASS"
echo "MT5_FOREX_LOCAL_BRIDGE_DIR=PASS"
