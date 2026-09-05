#!/usr/bin/env bash
set -euo pipefail
BASE="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v313-activate-new-listing-radar-safe.sh"
TMP="/tmp/meme-alpha-v318-activate.$$.sh"
[ -r "$BASE" ] || { echo V318_BASE_MISSING; exit 2; }
python3 - "$BASE" > "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
old='''      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js || echo "NEW_LISTING_RADAR_CYCLE_FAILED"'''
new='''      echo "RADAR_HEARTBEAT_START $(date -u +%Y-%m-%dT%H:%M:%SZ) user=$(id -un)" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || true\n      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1'''
if s.count(old)!=1: raise SystemExit('V318_RADAR_LOOP_ANCHOR_MISMATCH')
s=s.replace(old,new)
old2='''sudo -n /bin/systemctl restart "$SERVICE" || fail PAPER_RESTART_FAILED'''
new2='''# V318: pre-create the two non-sensitive runtime files because the service user\n# can overwrite files but intentionally cannot create arbitrary files in runtime-status.\nRSTATE="$APP/runtime-status/new-listing-radar.json"\nRLOG="$APP/runtime-status/new-listing-radar-runtime.log"\n: > "$RSTATE"\n: > "$RLOG"\nchmod 666 "$RSTATE" "$RLOG"\necho "V318_RUNTIME_FILES_READY state=$(stat -c %a "$RSTATE") log=$(stat -c %a "$RLOG")"\n\nsudo -n /bin/systemctl restart "$SERVICE" || fail PAPER_RESTART_FAILED'''
if s.count(old2)!=1: raise SystemExit('V318_RESTART_ANCHOR_MISMATCH')
s=s.replace(old2,new2)
old3='''[ "$radar_ok" -eq 1 ] || fail RADAR_NOT_HEALTHY'''
new3='''if [ "$radar_ok" -ne 1 ]; then\n  echo '=== V318 RADAR RUNTIME LOG ==='\n  tail -200 "$RLOG" 2>/dev/null || echo RADAR_RUNTIME_LOG_UNREADABLE\n  echo '=== V318 RADAR STATE ==='\n  head -120 "$RSTATE" 2>/dev/null || echo RADAR_STATE_UNREADABLE\n  echo '=== V318 SERVICE PROCESS SNAPSHOT ==='\n  ps -eo user,pid,ppid,stat,cmd | grep -E 'meme-alpha|new-listing-radar|run-paper' | grep -v grep | tail -100 || true\n  fail RADAR_NOT_HEALTHY\nfi'''
if s.count(old3)!=1: raise SystemExit('V318_HEALTH_ANCHOR_MISMATCH')
s=s.replace(old3,new3)
s=s.replace('V313_NEW_LISTING_RADAR_ACTIVE_PASS','V318_ALL_COMPONENTS_ACTIVE_PASS')
sys.stdout.write(s)
PY
/bin/bash -n "$TMP"
chmod 700 "$TMP"
exec /bin/bash "$TMP"
