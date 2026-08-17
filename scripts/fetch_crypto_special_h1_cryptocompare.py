#!/usr/bin/env python3
"""Public historical OHLC fetch only; no trading API."""
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
SYMS=('TAO','TON','IP');START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())-1
OUT='data/provider_snapshots/crypto_special_h1_jan_jul_2026_cryptocompare.json'
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-history/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
def fetch(s):
 ded={};to=END
 for _ in range(6):
  q=urllib.parse.urlencode({'fsym':s,'tsym':'USD','limit':2000,'toTs':to,'extraParams':'trading_api_project'});d=get('https://min-api.cryptocompare.com/data/v2/histohour?'+q)
  if d.get('Response')!='Success':raise RuntimeError((d.get('Message') or str(d))[:400])
  rows=((d.get('Data') or {}).get('Data') or [])
  if not rows:break
  oldest=min(int(x['time']) for x in rows)
  for x in rows:
   ts=int(x['time']); hi=float(x.get('high',0));lo=float(x.get('low',0));op=float(x.get('open',0));cl=float(x.get('close',0))
   if START<=ts<=END and hi>0 and lo>0 and op>0 and cl>0:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),op,hi,lo,cl]
  if oldest<=START:break
  to=oldest-3600;time.sleep(.25)
 return [ded[k] for k in sorted(ded)]
def main():
 data={};diag={}
 for s in SYMS:
  try:r=fetch(s);data[s]=r;diag[s]={'bars':len(r),'first':r[0][0] if r else None,'last':r[-1][0] if r else None}
  except Exception as e:data[s]=[];diag[s]={'error':str(e)}
 doc={'version':'CRYPTO_SPECIAL_H1_JAN_JUL_2026_CC_V1','provider':'CryptoCompare aggregate USD','interval':'1h','data':data,'diagnostics':diag,'fetchedAt':datetime.now(timezone.utc).isoformat()};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps(diag,indent=2),flush=True)
 if not any(data.values()):raise RuntimeError('no special H1 data')
if __name__=='__main__':main()
