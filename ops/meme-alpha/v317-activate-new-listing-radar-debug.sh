#!/usr/bin/env bash
set -euo pipefail
BASE="${GITHUB_WORKSPACE:-$(pwd)}/ops/meme-alpha/v313-activate-new-listing-radar-safe.sh"
TMP="/tmp/meme-alpha-v317-activate.$$.sh"
LOG="/tmp/meme-alpha-new-listing-radar.log"
[ -r "$BASE" ] || { echo V317_BASE_MISSING; exit 2; }
rm -f "$LOG" 2>/dev/null || true
python3 - "$BASE" > "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
old='''      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js || echo "NEW_LISTING_RADAR_CYCLE_FAILED"'''
new='''      echo "RADAR_HEARTBEAT_START $(date -u +%Y-%m-%dT%H:%M:%SZ) user=$(id -un)" >> /tmp/meme-alpha-new-listing-radar.log 2>&1 || true\n      /usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /tmp/meme-alpha-new-listing-radar.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /tmp/meme-alpha-new-listing-radar.log 2>&1'''
if s.count(old)!=1: raise SystemExit('V317_RUNNER_PATCH_ANCHOR_MISMATCH')
s=s.replace(old,new)
old2='''[ "$radar_ok" -eq 1 ] || fail RADAR_NOT_HEALTHY'''
new2='''if [ "$radar_ok" -ne 1 ]; then\n  echo '=== V317 RADAR RUNTIME LOG ==='\n  if [ -r /tmp/meme-alpha-new-listing-radar.log ]; then tail -160 /tmp/meme-alpha-new-listing-radar.log; else echo RADAR_RUNTIME_LOG_ABSENT; fi\n  echo '=== V317 SERVICE PROCESS SNAPSHOT ==='\n  ps -eo user,pid,ppid,stat,cmd | grep -E 'meme-alpha|new-listing-radar|run-paper' | grep -v grep | tail -80 || true\n  fail RADAR_NOT_HEALTHY\nfi'''
if s.count(old2)!=1: raise SystemExit('V317_HEALTH_PATCH_ANCHOR_MISMATCH')
s=s.replace(old2,new2)
sys.stdout.write(s)
PY
/bin/bash -n "$TMP"
chmod 700 "$TMP"
exec /bin/bash "$TMP"
