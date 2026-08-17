#!/usr/bin/env python3
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
START=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp());END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())-1;OUT='data/provider_snapshots/ton_h1_jan_jul_2026_cryptocompare.json'
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'trading-api-ton-h1/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
def main():
 ded={};to=END;pages=0
 while to>=START and pages<8:
  qs=urllib.parse.urlencode({'fsym':'TON','tsym':'USD','limit':2000,'toTs':to,'extraParams':'trading_api_project'});d=get('https://min-api.cryptocompare.com/data/v2/histohour?'+qs)
  if d.get('Response')!='Success':raise RuntimeError(str(d)[:1000])
  rows=((d.get('Data') or {}).get('Data') or [])
  if not rows:break
  oldest=min(int(x['time']) for x in rows)
  for x in rows:
   ts=int(x['time'])
   if START<=ts<=END and float(x.get('high',0))>0:
    ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x['open']),float(x['high']),float(x['low']),float(x['close'])]
  to=oldest-3600;pages+=1;print('PAGE',pages,'bars',len(ded),'oldest',datetime.fromtimestamp(oldest,timezone.utc).isoformat(),flush=True);time.sleep(.4)
  if oldest<=START:break
 rows=[ded[k] for k in sorted(ded)]
 if len(rows)<3000:raise RuntimeError(f'TON H1 insufficient {len(rows)}')
 doc={'version':'TON_H1_JAN_JUL_2026_CRYPTOCOMPARE_V1','provider':'CryptoCompare aggregate TON/USD','interval':'1h','bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'fetchedAt':datetime.now(timezone.utc).isoformat(),'data':{'TON':rows}};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({k:doc[k] for k in ('version','bars','first','last')},indent=2),flush=True)
if __name__=='__main__':main()
