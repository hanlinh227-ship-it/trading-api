#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
SYMS='AAVE AVAX DOT FLOKI INJ LDO LIT ONDO POL S TAO WLD XPL'.split()
START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,4,1,tzinfo=timezone.utc).timestamp())-1;OUT='data/provider_snapshots/crypto_remaining13_h1_jan_mar_2026.json';UA='trading-api-rem13-h1/1.0'
def get(url,retries=5):
 last=None
 for n in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
  except Exception as e:last=e;time.sleep(.6*(n+1))
 raise RuntimeError(str(last))
def okx(s):
 cur=END*1000;ded={};pages=0
 while cur>=START*1000 and pages<35:
  qs=urllib.parse.urlencode({'instId':f'{s}-USDT','bar':'1H','after':str(cur),'limit':'100'});d=get('https://www.okx.com/api/v5/market/history-candles?'+qs)
  if d.get('code')!='0':raise RuntimeError(str(d)[:500])
  rows=d.get('data') or []
  if not rows:break
  old=min(int(x[0])//1000 for x in rows)
  for x in rows:
   ts=int(x[0])//1000
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  cur=old*1000-1;pages+=1;time.sleep(.10)
  if old<START:break
 return [ded[k] for k in sorted(ded)],'OKX'
def gate(s):
 ded={};cur=START;chunk=900*3600
 while cur<=END:
  to=min(END,cur+chunk);qs=urllib.parse.urlencode({'currency_pair':f'{s}_USDT','interval':'1h','from':cur,'to':to,'limit':'1000'});d=get('https://api.gateio.ws/api/v4/spot/candlesticks?'+qs)
  if isinstance(d,dict):raise RuntimeError(str(d)[:500])
  for x in d or []:
   ts=int(x[0])
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[5]),float(x[3]),float(x[4]),float(x[2])]
  cur=to+1;time.sleep(.12)
 return [ded[k] for k in sorted(ded)],'GATE'
def one(s):
 best=None
 for fn in (okx,gate):
  try:
   rows,src=fn(s)
   if best is None or len(rows)>len(best[0]):best=(rows,src)
   if len(rows)>=720:return s,rows,src
  except Exception:pass
 return s,(best[0] if best else []),(best[1] if best else 'NONE')
def main():
 data={};diag={};missing={}
 with ThreadPoolExecutor(max_workers=5) as ex:
  fs=[ex.submit(one,s) for s in SYMS]
  for f in as_completed(fs):
   s,rows,src=f.result()
   if len(rows)>=720:
    data[s]=rows;diag[s]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0]};print('FOUND',s,src,len(rows),rows[0][0],flush=True)
   else:missing[s]=len(rows);print('MISSING',s,len(rows),flush=True)
 doc={'version':'CRYPTO_REMAINING13_H1_JAN_MAR_2026_V1','requested':SYMS,'coverageCount':len(data),'coveredSymbols':sorted(data),'missing':missing,'diagnostics':diag,'data':data};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'coverage':len(data),'covered':sorted(data),'missing':missing},indent=2),flush=True)
 if len(data)<8:raise RuntimeError('Too little coverage')
if __name__=='__main__':main()
