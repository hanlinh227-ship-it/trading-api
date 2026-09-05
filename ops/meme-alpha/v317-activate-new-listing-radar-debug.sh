#!/usr/bin/env bash
set -euo pipefail
BASE="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v313-activate-new-listing-radar-safe.sh"
TMP="/tmp/meme-alpha-v320-activate.$$.sh"
[ -r "$BASE" ] || { echo V320_BASE_MISSING; exit 2; }
python3 - "$BASE" > "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
old0='''/usr/bin/node --check "$rtmp"\nmv -f "$rtmp" "$RADAR"'''
new0='''/usr/bin/node --check "$rtmp"\nmv -f "$rtmp" "$RADAR"\nchmod 644 "$RADAR"\necho "V320_RADAR_FILE_READY $(stat -c 'owner=%U group=%G mode=%a size=%s' "$RADAR")"'''
if s.count(old0)!=1: raise SystemExit('V320_RADAR_INSTALL_ANCHOR_MISMATCH')
s=s.replace(old0,new0)
old_sc='''/usr/bin/node --check "$stmp"\nmv -f "$stmp" "$SCANNER"'''
new_sc='''/usr/bin/node --check "$stmp"\nmv -f "$stmp" "$SCANNER"\nchmod 644 "$SCANNER"\necho "V320_SCANNER_FILE_READY $(stat -c 'owner=%U group=%G mode=%a size=%s' "$SCANNER")"'''
if s.count(old_sc)!=1: raise SystemExit('V320_SCANNER_INSTALL_ANCHOR_MISMATCH')
s=s.replace(old_sc,new_sc)
old='''      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js || echo "NEW_LISTING_RADAR_CYCLE_FAILED"'''
new='''      echo "RADAR_HEARTBEAT_START $(date -u +%Y-%m-%dT%H:%M:%SZ) user=$(id -un)" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || true\n      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1'''
if s.count(old)!=1: raise SystemExit('V320_RADAR_LOOP_ANCHOR_MISMATCH')
s=s.replace(old,new)
old2='''sudo -n /bin/systemctl restart "$SERVICE" || fail PAPER_RESTART_FAILED'''
new2='''RSTATE="$APP/runtime-status/new-listing-radar.json"\nRLOG="$APP/runtime-status/new-listing-radar-runtime.log"\n: > "$RSTATE"\n: > "$RLOG"\nchmod 666 "$RSTATE" "$RLOG" 2>/dev/null || true\necho "V320_RUNTIME_FILES_READY state=$(stat -c '%U:%G:%a' "$RSTATE") log=$(stat -c '%U:%G:%a' "$RLOG")"\n\nsudo -n /bin/systemctl restart "$SERVICE" || fail PAPER_RESTART_FAILED'''
if s.count(old2)!=1: raise SystemExit('V320_RESTART_ANCHOR_MISMATCH')
s=s.replace(old2,new2)
old3='''[ "$radar_ok" -eq 1 ] || fail RADAR_NOT_HEALTHY'''
new3='''if [ "$radar_ok" -ne 1 ]; then\n  echo '=== V320 RADAR RUNTIME LOG ==='\n  tail -200 "$RLOG" 2>/dev/null || echo RADAR_RUNTIME_LOG_UNREADABLE\n  echo '=== V320 RADAR STATE ==='\n  head -120 "$RSTATE" 2>/dev/null || echo RADAR_STATE_UNREADABLE\n  echo '=== V320 SERVICE PROCESS SNAPSHOT ==='\n  ps -eo user,pid,ppid,stat,cmd | grep -E 'meme-alpha|new-listing-radar|run-paper|scanner' | grep -v grep | tail -120 || true\n  fail RADAR_NOT_HEALTHY\nfi'''
if s.count(old3)!=1: raise SystemExit('V320_HEALTH_ANCHOR_MISMATCH')
s=s.replace(old3,new3)
old4='''[ "$sig_ok" -eq 1 ] || fail SIGNAL_NOT_HEALTHY'''
new4='''if [ "$sig_ok" -ne 1 ]; then\n  echo '=== V320 SIGNAL VERIFY FAILED ==='\n  tail -200 "$RLOG" 2>/dev/null || true\n  ps -eo user,pid,ppid,stat,cmd | grep -E 'meme-alpha|new-listing-radar|run-paper|scanner' | grep -v grep | tail -120 || true\n  fail SIGNAL_NOT_HEALTHY\nfi'''
if s.count(old4)!=1: raise SystemExit('V320_SIGNAL_HEALTH_ANCHOR_MISMATCH')
s=s.replace(old4,new4)
s=s.replace('V313_NEW_LISTING_RADAR_ACTIVE_PASS','V320_ALL_COMPONENTS_ACTIVE_PASS')
sys.stdout.write(s)
PY
/bin/bash -n "$TMP"
chmod 700 "$TMP"
exec /bin/bash "$TMP"
