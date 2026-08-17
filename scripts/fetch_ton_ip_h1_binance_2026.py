#!/usr/bin/env python3
"""Fetch public historical OHLC only; no authenticated trading API."""
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp()*1000);END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp()*1000)-1
OUT='data/provider_snapshots/ton_ip_h1_jan_jul_2026_binance.json';SYMS=('TON','IP')
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-history/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
def fetch(sym):
 cur=START;out=[]
 while cur<=END:
  q=urllib.parse.urlencode({'symbol':sym+'USDT','interval':'1h','startTime':cur,'endTime':END,'limit':1000})
  rows=get('https://data-api.binance.vision/api/v3/klines?'+q)
  if not rows:break
  for x in rows:
   ts=int(x[0]);out.append([datetime.fromtimestamp(ts/1000,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])])
  nxt=int(rows[-1][0])+3600000
  if nxt<=cur:break
  cur=nxt;time.sleep(.15)
 return out
def main():
 data={};diag={}
 for s in SYMS:
  try:r=fetch(s)
  except Exception as e:r=[];diag[s]={'error':str(e)}
  data[s]=r
  if r:diag[s]={'bars':len(r),'first':r[0][0],'last':r[-1][0]}
 doc={'version':'TON_IP_H1_JAN_JUL_2026_BINANCE_V1','provider':'Binance public market data','interval':'1h','data':data,'diagnostics':diag,'fetchedAt':datetime.now(timezone.utc).isoformat()};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps(diag,indent=2),flush=True)
 if not any(data.values()):raise RuntimeError('No TON/IP public H1 data returned')
if __name__=='__main__':main()
