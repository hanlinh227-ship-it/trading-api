#!/usr/bin/env python3
import json,os,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
OUT='data/provider_snapshots/ton_h1_feb_jul_2026_twelvedata.json'
def main():
 key=os.environ.get('TWELVEDATA_API_KEY','').strip()
 if not key:raise RuntimeError('TWELVEDATA_API_KEY missing')
 # <5000 hourly bars, enough for multiple full-month walk-forward stages.
 qs=urllib.parse.urlencode({'symbol':'TON/USD','interval':'1h','outputsize':5000,'start_date':'2026-02-01 00:00:00','end_date':'2026-07-31 23:59:59','timezone':'UTC','order':'asc','apikey':key})
 req=urllib.request.Request('https://api.twelvedata.com/time_series?'+qs,headers={'User-Agent':'trading-api-ton-h1-td/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:d=json.loads(r.read().decode())
 vals=d.get('values') or []
 rows=sorted([[x['datetime'],float(x['open']),float(x['high']),float(x['low']),float(x['close'])] for x in vals])
 if len(rows)<3500:raise RuntimeError(f'TON/USD insufficient {len(rows)} response={str(d)[:700]}')
 doc={'version':'TON_H1_FEB_JUL_2026_TWELVEDATA_V1','provider':'Twelve Data','symbol':'TON/USD','interval':'1h','bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'fetchedAt':datetime.now(timezone.utc).isoformat(),'data':{'TON':rows}}
 Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({k:doc[k] for k in ('version','bars','first','last')},indent=2))
if __name__=='__main__':main()
