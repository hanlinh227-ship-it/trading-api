#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.12 SCANNER STALE DIAGNOSTIC ==='
for u in meme-alpha-paper.service meme-alpha-trend-pulse.service meme-alpha-micro-live.service meme-alpha-signer.service; do
  echo "UNIT=$u ACTIVE=$(systemctl is-active "$u" 2>/dev/null || true) PID=$(systemctl show "$u" -p MainPID --value 2>/dev/null || true) START=$(systemctl show "$u" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
done

echo '--- RUNTIME FILE AGES ---'
python3 - <<'PY'
import os,time,json,glob
for p in sorted(glob.glob('/opt/meme-alpha/app/runtime-status/*')):
 try:
  st=os.stat(p);print(f'{os.path.basename(p)} age={time.time()-st.st_mtime:.1f}s size={st.st_size}')
 except:pass
PY

echo '--- PAPER SERVICE STATUS ---'
systemctl status meme-alpha-paper.service --no-pager -l 2>&1 | tail -n 40 || true

echo '--- PAPER JOURNAL LAST 120 ---'
journalctl -u meme-alpha-paper.service -n 120 --no-pager -o short-iso 2>&1 || true

echo '--- LOG FILES ---'
find /var/log/meme-alpha -maxdepth 1 -type f -printf '%f %s bytes\n' 2>/dev/null | sort || true
for f in /var/log/meme-alpha/*paper* /var/log/meme-alpha/*scanner* /var/log/meme-alpha/*source*; do
 [ -f "$f" ] || continue
 echo "--- TAIL $f ---"; tail -n 80 "$f" || true
done

echo '--- PROCESSES ---'
ps -eo pid,ppid,etimes,stat,%cpu,%mem,cmd | grep -E 'meme-alpha|node|python3' | grep -v grep | head -n 80 || true

echo V212_SCANNER_STALE_DIAGNOSTIC_PASS
