#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
SYMS=['TAO','TON','GRASS','IP','LIT'];START=int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())-1;OUT='data/provider_snapshots/crypto_missing5_4h_2025.json';UA='trading-api-missing5/1.0'
def get(url,retries=5):
 last=None
 for n in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
  except Exception as e:last=e;time.sleep(.7*(n+1))
 raise RuntimeError(str(last))
def gate(sym):
 ded={};cur=START;pages=0;chunk=950*4*3600
 while cur<=END:
  to=min(END,cur+chunk);qs=urllib.parse.urlencode({'currency_pair':f'{sym}_USDT','interval':'4h','from':cur,'to':to,'limit':'1000'});d=get('https://api.gateio.ws/api/v4/spot/candlesticks?'+qs)
  if isinstance(d,dict):raise RuntimeError('GATE '+str(d)[:400])
  for x in d or []:
   ts=int(x[0])
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[5]),float(x[3]),float(x[4]),float(x[2])]
  cur=to+1;pages+=1;time.sleep(.15)
 return [ded[k] for k in sorted(ded)],'GATE'
def mexc(sym):
 # MEXC max 1000, walk by start/end milliseconds.
 ded={};cur=START*1000;end=END*1000;step=999*4*3600*1000;pages=0
 while cur<=end:
  to=min(end,cur+step);qs=urllib.parse.urlencode({'symbol':sym+'USDT','interval':'4h','startTime':cur,'endTime':to,'limit':1000});d=get('https://api.mexc.com/api/v3/klines?'+qs)
  if isinstance(d,dict):raise RuntimeError('MEXC '+str(d)[:400])
  for x in d or []:
   ts=int(x[0])//1000
   if START<=ts<=END:ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
  cur=to+1;pages+=1;time.sleep(.15)
 return [ded[k] for k in sorted(ded)],'MEXC'
def main():
 data={};diag={};errors={}
 for s in SYMS:
  best=None
  for fn in (gate,mexc):
   try:
    rows,src=fn(s)
    if best is None or len(rows)>len(best[0]):best=(rows,src)
    if len(rows)>=180:break
   except Exception as e:errors.setdefault(s,[]).append(str(e))
  if best and len(best[0])>=180:
   rows,src=best;data[s]=rows;diag[s]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0]};print('FOUND',s,src,len(rows),rows[0][0],rows[-1][0],flush=True)
  else:print('MISSING',s,'best',len(best[0]) if best else 0,errors.get(s),flush=True)
 doc={'version':'CRYPTO_MISSING5_4H_2025_V1','requested':SYMS,'coverageCount':len(data),'diagnostics':diag,'errors':errors,'data':data};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'coverage':len(data),'diagnostics':diag,'errors':errors},indent=2),flush=True)
 if len(data)<4:raise RuntimeError('Insufficient missing5 recovery')
if __name__=='__main__':main()
