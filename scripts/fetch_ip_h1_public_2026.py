#!/usr/bin/env python3
"""Fetch public historical OHLC for IP only; no authenticated trading API."""
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000);END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp()*1000)-1
OUT='data/provider_snapshots/ip_h1_jan_jul_2026_public.json'
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-history/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
def bybit():
 end=END;ded={}
 for _ in range(8):
  q=urllib.parse.urlencode({'category':'spot','symbol':'IPUSDT','interval':'60','end':end,'limit':1000});d=get('https://api.bybit.com/v5/market/kline?'+q)
  if str(d.get('retCode'))!='0':raise RuntimeError(d.get('retMsg') or str(d)[:300])
  rows=((d.get('result') or {}).get('list') or [])
  if not rows:break
  oldest=min(int(x[0]) for x in rows)
  for x in rows:
   ts=int(x[0]);
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  if oldest<=START:break
  end=oldest-1;time.sleep(.15)
 return [ded[k] for k in sorted(ded)]
def okx():
 after=END;ded={}
 for _ in range(60):
  q=urllib.parse.urlencode({'instId':'IP-USDT','bar':'1H','after':after,'limit':100});d=get('https://www.okx.com/api/v5/market/history-candles?'+q)
  if str(d.get('code'))!='0':raise RuntimeError(d.get('msg') or str(d)[:300])
  rows=d.get('data') or []
  if not rows:break
  oldest=min(int(x[0]) for x in rows)
  for x in rows:
   ts=int(x[0]);
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  if oldest<=START:break
  after=oldest-1;time.sleep(.12)
 return [ded[k] for k in sorted(ded)]
def main():
 diag={};data=[];provider=None
 for name,fn in [('Bybit spot',bybit),('OKX spot',okx)]:
  try:
   r=fn();diag[name]={'bars':len(r),'first':r[0][0] if r else None,'last':r[-1][0] if r else None}
   if len(r)>len(data):data=r;provider=name
  except Exception as e:diag[name]={'error':str(e)}
 doc={'version':'IP_H1_JAN_JUL_2026_PUBLIC_V1','provider':provider,'interval':'1h','data':{'IP':data},'diagnostics':diag,'fetchedAt':datetime.now(timezone.utc).isoformat()};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps(diag,indent=2),flush=True)
 if len(data)<1000:raise RuntimeError('Insufficient IP H1 history')
if __name__=='__main__':main()
