#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
F="$APP/run-paper.sh"
B="$APP/runtime-status/run-paper-pre-v340-$(date -u +%Y%m%dT%H%M%SZ).sh"
cp -a "$F" "$B"
rollback(){ rc=$?; if [ $rc -ne 0 ]; then cp -a "$B" "$F" || true; chmod 0775 "$F" || true; sudo /bin/systemctl restart meme-alpha-paper.service || true; echo V340_ROLLBACK_DONE=TRUE; fi; exit $rc; }
trap rollback EXIT
python3 - "$F" <<'PY'
from pathlib import Path
p=Path(__import__('sys').argv[1]); s=p.read_text()
if 'LIVE_SIGNAL_MAX_AGE_SEC=6' not in s: raise SystemExit('EXPECTED_6S_FRESHNESS_NOT_FOUND')
s=s.replace('LIVE_SIGNAL_MAX_AGE_SEC=6','LIVE_SIGNAL_MAX_AGE_SEC=60',1)
needle="  close_entry_gate 'FULL_CYCLE_REFRESH_IN_PROGRESS'\n"
if needle not in s: raise SystemExit('EXPECTED_FULL_CYCLE_GATE_CLOSE_NOT_FOUND')
s=s.replace(needle,"  echo 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH'\n",1)
needle2='    echo "FULL_CYCLE_FAILED rc=$rc"\n'
if needle2 not in s: raise SystemExit('FAIL_BRANCH_NOT_FOUND')
s=s.replace(needle2,needle2+"    close_entry_gate 'FULL_CYCLE_FAILED'\n",1)
p.write_text(s)
PY
chmod 0775 "$F"
# invariants
! grep -q '/usr/bin/node src/position.js' "$F"
grep -q 'paperExecutionEnabled:false' "$F"
grep -q 'LIVE_SIGNAL_MAX_AGE_SEC=60' "$F"
grep -q 'CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH' "$F"
grep -q "close_entry_gate 'FULL_CYCLE_FAILED'" "$F"
# restart only the scanner service; executor/signer untouched
sudo /bin/systemctl restart meme-alpha-paper.service
sleep 3
sudo /bin/systemctl is-active --quiet meme-alpha-paper.service
echo V340_CONTINUITY_SCAN_ACTIVE=TRUE
trap - EXIT
