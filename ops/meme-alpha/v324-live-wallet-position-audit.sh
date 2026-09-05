#!/usr/bin/env bash
set -euo pipefail
APP=/opt/meme-alpha/app

echo '=== V324 LIVE WALLET / POSITION AUDIT ==='
date -u +NOW_UTC=%Y-%m-%dT%H:%M:%SZ

echo '=== EXECUTOR STATE/PATH REFERENCES (REDACTED) ==='
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/meme-alpha/app/src/micro-live-executor.js')
if p.exists():
    for i,line in enumerate(p.read_text(errors='ignore').splitlines(),1):
        low=line.lower()
        if any(k in low for k in ['state','position','trade','fill','journal','ledger','wallet','balance','rpc','signer','policy']):
            # Skip likely secret-bearing environment/token lines.
            if any(k in low for k in ['secret','private','mnemonic','api_key','apikey','authorization','bearer']):
                continue
            print(f'{i}: {line[:350]}')
PY

echo '=== CANDIDATE STATE FILES ==='
for root in /var/lib/meme-alpha /opt/meme-alpha/app/state /opt/meme-alpha/app/runtime-status /opt/meme-alpha-signer; do
  [ -d "$root" ] || continue
  echo "ROOT=$root"
  find "$root" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %u:%g %m %p\n' 2>/dev/null | sort -r | head -120
done

echo '=== SAFE STATE CONTENT SUMMARIES ==='
python3 - <<'PY'
import os,json,re,time
roots=['/var/lib/meme-alpha','/opt/meme-alpha/app/state','/opt/meme-alpha/app/runtime-status']
allow=re.compile(r'(balance|equity|available|position|open|closed|side|entry|mark|pnl|profit|loss|trade|buy|sell|fill|order|signature|tx|mint|symbol|price|amount|qty|size|status|reason|timestamp|updated|created|wallet|owner|sol|usd|lamport)',re.I)
deny=re.compile(r'(secret|private|seed|mnemonic|keypair|token|api.?key|authorization|password)',re.I)

def sanitize(x,depth=0):
    if depth>5:return '<nested>'
    if isinstance(x,dict):
        out={}
        for k,v in x.items():
            if deny.search(str(k)):continue
            if allow.search(str(k)) or depth>0:
                out[k]=sanitize(v,depth+1)
        return out
    if isinstance(x,list): return [sanitize(v,depth+1) for v in x[:12]]
    if isinstance(x,str): return x[:220]
    return x

seen=0
for root in roots:
  if not os.path.isdir(root): continue
  for d,_,names in os.walk(root):
    for n in names:
      p=os.path.join(d,n)
      try:
        st=os.stat(p)
      except: continue
      if st.st_size>2_000_000: continue
      if not (n.endswith('.json') or n.endswith('.jsonl') or n.endswith('.ndjson')): continue
      if time.time()-st.st_mtime>14*86400: continue
      try:
        if n.endswith('.json'):
          obj=json.load(open(p,encoding='utf-8'))
          safe=sanitize(obj)
          txt=json.dumps(safe,ensure_ascii=False,separators=(',',':'))
          if txt not in ('{}','[]'):
            print('FILE='+p); print(txt[:12000]); seen+=1
        else:
          lines=open(p,encoding='utf-8',errors='ignore').read().splitlines()[-30:]
          out=[]
          for ln in lines:
            try: out.append(sanitize(json.loads(ln)))
            except: pass
          if out:
            print('FILE='+p); print(json.dumps(out,ensure_ascii=False,separators=(',',':'))[:16000]); seen+=1
      except Exception:
        pass
      if seen>=80: raise SystemExit
PY

echo '=== SIGNER PUBLIC STATUS PROBES ==='
# Probe localhost endpoints only; do not print environment or secret material.
for u in http://127.0.0.1:8787/health http://127.0.0.1:8787/status http://127.0.0.1:8788/health http://127.0.0.1:8788/status; do
  code=$(curl -sS --max-time 2 -o /tmp/v324-probe.$$ -w '%{http_code}' "$u" 2>/dev/null || true)
  if [ "$code" != "000" ]; then
    echo "PROBE=$u HTTP=$code"
    head -c 2000 /tmp/v324-probe.$$ 2>/dev/null | sed -E 's/(secret|privateKey|mnemonic|seed|apiKey)"?[[:space:]]*:[[:space:]]*"[^"]+"/\1":"<redacted>"/Ig' || true
    echo
  fi
done
rm -f /tmp/v324-probe.$$ 2>/dev/null || true

echo V324_LIVE_WALLET_POSITION_AUDIT_PASS
