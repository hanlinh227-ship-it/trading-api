#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app
RT="$APP/runtime-status"

echo '=== V323 MEME ALPHA RUNTIME / ACCOUNT / CONFLICT AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ

# Read-only service/process inspection.
echo '=== SERVICES ==='
for s in meme-alpha-paper.service meme-alpha-trend-pulse.service meme-alpha-micro-live-executor.service meme-alpha-signer.service; do
  x=$(sudo -n /bin/systemctl is-active "$s" 2>/dev/null || true)
  [ -n "$x" ] && echo "$s=$x"
done

echo '=== PROCESS COUNTS ==='
python3 - <<'PY'
import subprocess
patterns={
 'paper':'/opt/meme-alpha/app/run-paper.sh',
 'trend':'/opt/meme-alpha/app/src/trend-pulse.js',
 'executor':'/opt/meme-alpha/app/src/micro-live-executor.js',
 'signer':'/opt/meme-alpha-signer/ready_signer.py',
 'radar':'/opt/meme-alpha/app/src/new-listing-radar.js',
}
out=subprocess.check_output(['ps','-eo','pid,ppid,user,stat,args'], text=True)
for k,p in patterns.items():
    rows=[r for r in out.splitlines() if p in r and 'v323-runtime-account-conflict-audit' not in r]
    print(f'{k.upper()}_PROC_COUNT={len(rows)}')
    for r in rows[:6]: print('  '+r.strip())
PY

echo '=== SYSTEMD RESTART COUNTERS ==='
for s in meme-alpha-paper.service meme-alpha-trend-pulse.service meme-alpha-micro-live-executor.service meme-alpha-signer.service; do
  if sudo -n /bin/systemctl show "$s" >/dev/null 2>&1; then
    sudo -n /bin/systemctl show "$s" -p ActiveState -p SubState -p NRestarts -p ExecMainStatus -p ExecMainStartTimestamp --no-pager 2>/dev/null || true
  fi
done

echo '=== RECENT RUNTIME FILES ==='
find "$RT" -maxdepth 2 -type f -printf '%T@ %TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' 2>/dev/null | sort -nr | head -80

echo '=== SAFE JSON SUMMARIES ==='
python3 - "$RT" <<'PY'
import json, os, sys, time, re
rt=sys.argv[1]
allow=re.compile(r'(balance|equity|available|position|open|side|entry|mark|pnl|profit|loss|trade|buy|sell|fill|order|signature|tx|mint|symbol|price|amount|qty|size|status|reason|timestamp|updated|created|wallet|sol|usd)', re.I)
deny=re.compile(r'(secret|private|seed|mnemonic|keypair|token|api.?key|authorization|password)', re.I)

def safe(v, depth=0):
    if depth>3: return '<nested>'
    if isinstance(v, dict):
        out={}
        for k,x in v.items():
            if deny.search(str(k)): continue
            if allow.search(str(k)):
                out[k]=safe(x, depth+1)
        return out
    if isinstance(v, list): return [safe(x, depth+1) for x in v[:8]]
    if isinstance(v, str): return v[:180]
    if isinstance(v, (int,float,bool)) or v is None: return v
    return str(v)[:180]

files=[]
for root,dirs,names in os.walk(rt):
    for n in names:
        p=os.path.join(root,n)
        if not n.endswith('.json'): continue
        try:
            st=os.stat(p)
            if time.time()-st.st_mtime > 7*86400: continue
            files.append((st.st_mtime,p))
        except: pass
for _,p in sorted(files, reverse=True)[:60]:
    try:
        with open(p,'r',encoding='utf-8') as f: obj=json.load(f)
    except Exception as e:
        continue
    s=safe(obj)
    if s and s!={} and s!=[]:
        print('FILE='+p)
        print(json.dumps(s, ensure_ascii=False, separators=(',',':'))[:5000])
PY

echo '=== RECENT TEXT/JOURNAL HINTS ==='
find "$APP" -maxdepth 3 -type f \( -iname '*trade*' -o -iname '*order*' -o -iname '*fill*' -o -iname '*position*' -o -iname '*journal*' -o -iname '*ledger*' -o -iname '*executor*' \) -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' 2>/dev/null | sort -r | head -100

echo V323_RUNTIME_ACCOUNT_CONFLICT_AUDIT_PASS
