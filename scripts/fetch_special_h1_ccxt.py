#!/usr/bin/env python3
"""Public OHLC fallback via CCXT; no auth, no order methods."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
import ccxt
SYMS=('IP','TON');START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000);END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp()*1000)-1
OUT='data/provider_snapshots/ip_ton_h1_jan_jul_2026_ccxt.json';EXCH=('gateio','kucoin','bitget','mexc','bybit','okx')
def fetch(exid,sym):
 ex=getattr(ccxt,exid)({'enableRateLimit':True,'timeout':20000});ex.load_markets();pair=sym+'/USDT'
 if pair not in ex.markets:return [],'pair missing'
 cur=START;ded={};loops=0
 while cur<=END and loops<30:
  loops+=1;rows=ex.fetch_ohlcv(pair,'1h',since=cur,limit=1000)
  if not rows:break
  last=None
  for x in rows:
   ts=int(x[0]);last=ts
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  if last is None or last<cur:break
  nxt=last+3600000
  if nxt<=cur:break
  cur=nxt
  if last>=END:break
  time.sleep(ex.rateLimit/1000 if ex.rateLimit else .1)
 return [ded[k] for k in sorted(ded)],None
def main():
 data={};diag={}
 for sym in SYMS:
  best=[];prov=None;diag[sym]={}
  for exid in EXCH:
   try:r,why=fetch(exid,sym);diag[sym][exid]={'bars':len(r),'first':r[0][0] if r else None,'last':r[-1][0] if r else None,'note':why}
   except Exception as e:r=[];diag[sym][exid]={'error':str(e)[:400]}
   if len(r)>len(best):best=r;prov=exid
   if len(best)>=5000:break
  data[sym]=best;diag[sym]['selected']=prov
 doc={'version':'IP_TON_H1_JAN_JUL_2026_CCXT_V1','providerBySymbol':{s:diag[s].get('selected') for s in SYMS},'interval':'1h','data':data,'diagnostics':diag,'fetchedAt':datetime.now(timezone.utc).isoformat()};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps(diag,indent=2),flush=True)
 if not any(len(data[s])>=1000 for s in SYMS):raise RuntimeError('No sufficient public H1 history')
if __name__=='__main__':main()
