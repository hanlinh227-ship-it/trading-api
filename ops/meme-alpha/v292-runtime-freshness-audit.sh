#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
cd "$APP"
echo '=== MEME ALPHA v2.9.2 RUNTIME FRESHNESS AUDIT ==='
for u in meme-alpha-paper.service meme-alpha-trend-pulse.service meme-alpha-signer.service meme-alpha-micro-live.service; do
  echo "UNIT=$u ACTIVE=$(systemctl is-active "$u" 2>/dev/null || true) PID=$(systemctl show "$u" -p MainPID --value 2>/dev/null || true) START=$(systemctl show "$u" -p ExecMainStartTimestamp --value 2>/dev/null || true)"
done
python3 - <<'PY'
import json,os,time
files=['runtime-status/signal-snapshot.json','runtime-status/micro-live-gate.json','runtime-status/source-health.json','runtime-status/trend-pulse.json']
for p in files:
 ap='/opt/meme-alpha/app/'+p
 try:
  st=os.stat(ap); x=json.load(open(ap)); age=time.time()-st.st_mtime
  print(f'FILE={p} AGE_SEC={age:.1f} TS={x.get("timestamp")}')
  if p.endswith('micro-live-gate.json'):
   print('GATE_ALLOWED='+str(x.get('allowed'))+' GATE_REASONS='+(','.join(x.get('reasons',[])) or 'NONE')+' EXEC='+str(x.get('executionMode')))
  if p.endswith('source-health.json'):
   print('SOURCE_STATUS='+str(x.get('status'))+' HEALTHY='+str(x.get('healthy'))+' USING_CACHE='+str(x.get('usingCache'))+' SOURCES='+str(x.get('activeSources') or x.get('sources')))
  if p.endswith('signal-snapshot.json'):
   print('SIGNAL_CANDIDATES='+str(len(x.get('candidates',[]) or [])))
  if p.endswith('trend-pulse.json'):
   print('TREND_TOP='+str((x.get('themes') or [{}])[0].get('narrative','NONE'))+' STRENGTH='+str((x.get('themes') or [{}])[0].get('strength',0)))
 except Exception as e: print(f'FILE={p} ERROR={e}')
PY

echo '=== PAPER LOG TAIL ==='
tail -n 120 /var/log/meme-alpha/paper.log 2>/dev/null || true
echo '=== PAPER ERROR TAIL ==='
tail -n 120 /var/log/meme-alpha/paper-error.log 2>/dev/null || true
echo '=== TREND ERROR TAIL ==='
tail -n 80 /var/log/meme-alpha/trend-pulse-error.log 2>/dev/null || true
echo '=== MICRO LOG TAIL ==='
tail -n 100 /var/log/meme-alpha/micro-live.log 2>/dev/null || true
echo V292_RUNTIME_FRESHNESS_AUDIT_PASS
