#!/usr/bin/env bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo V341_FAIL=ROOT_REQUIRED; exit 1; }
APP=/opt/meme-alpha/app
F="$APP/run-paper.sh"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
B="$APP/runtime-status/run-paper-pre-v341-$STAMP.sh"
cp -a "$F" "$B"
rollback(){ rc=$?; if [ $rc -ne 0 ]; then echo V341_ROLLBACK_START=TRUE; cp -a "$B" "$F" || true; chmod 0775 "$F" || true; systemctl restart meme-alpha-paper.service || true; echo V341_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
python3 - "$F" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
# idempotent or upgrade from v328/v340 rollback baseline
if 'LIVE_SIGNAL_MAX_AGE_SEC=6' in s:
    s=s.replace('LIVE_SIGNAL_MAX_AGE_SEC=6','LIVE_SIGNAL_MAX_AGE_SEC=60',1)
elif 'LIVE_SIGNAL_MAX_AGE_SEC=60' not in s:
    raise SystemExit('FRESHNESS_SETTING_UNKNOWN')
needle="  close_entry_gate 'FULL_CYCLE_REFRESH_IN_PROGRESS'\n"
if needle in s:
    s=s.replace(needle,"  echo 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH'\n",1)
elif 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH' not in s:
    raise SystemExit('FULL_CYCLE_GATE_TOPOLOGY_UNKNOWN')
needle2='    echo "FULL_CYCLE_FAILED rc=$rc"\n'
if "close_entry_gate 'FULL_CYCLE_FAILED'" not in s:
    if needle2 not in s: raise SystemExit('FAIL_BRANCH_NOT_FOUND')
    s=s.replace(needle2,needle2+"    close_entry_gate 'FULL_CYCLE_FAILED'\n",1)
p.write_text(s)
PY
chmod 0775 "$F"
! grep -q '/usr/bin/node src/position.js' "$F"
grep -q 'paperExecutionEnabled:false' "$F"
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=60' "$F"
grep -q 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH' "$F"
grep -q "close_entry_gate 'FULL_CYCLE_FAILED'" "$F"
systemctl restart meme-alpha-paper.service
sleep 5
systemctl is-active --quiet meme-alpha-paper.service
[ "$(pgrep -fc '/usr/bin/node /opt/meme-alpha/app/src/micro-live-executor.js' || true)" -eq 1 ]
[ "$(pgrep -fc '/usr/bin/python3 /opt/meme-alpha-signer/ready_signer.py' || true)" -eq 1 ]
echo V341_CONTINUITY_SCAN_PRODUCTION_ACTIVE=TRUE
trap - EXIT
