#!/usr/bin/env python3
import json,os,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
OUT='data/provider_snapshots/eurusd_h1_oct2024_final.json'
def main():
 key=os.environ.get('TWELVEDATA_API_KEY','').strip()
 if not key:raise RuntimeError('TWELVEDATA_API_KEY missing')
 qs=urllib.parse.urlencode({'symbol':'EUR/USD','interval':'1h','outputsize':1200,'start_date':'2024-09-20 00:00:00','end_date':'2024-11-03 23:59:59','timezone':'UTC','order':'asc','apikey':key})
 req=urllib.request.Request('https://api.twelvedata.com/time_series?'+qs,headers={'User-Agent':'trading-api-eurusd-final/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:d=json.loads(r.read().decode())
 vals=d.get('values') or []
 z=sorted([[x['datetime'],float(x['open']),float(x['high']),float(x['low']),float(x['close'])] for x in vals])
 if len(z)<700:raise RuntimeError(f'insufficient EURUSD final bars {len(z)} response={str(d)[:500]}')
 doc={'version':'EURUSD_H1_OCT2024_FINAL_V1','provider':'Twelve Data','signalMonth':'2024-10-01..2024-10-31','warmupFrom':'2024-09-20','outcomeBufferThrough':'2024-11-03','lockedCheckpoint':'docs/checkpoints/FOREX_EURUSD_V32_PRE_2024_LOCK.md','fetchedAt':datetime.now(timezone.utc).isoformat(),'bars':len(z),'first':z[0][0],'last':z[-1][0],'data':{'EURUSD':z}}
 Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({k:doc[k] for k in ('version','bars','first','last','signalMonth')},indent=2))
if __name__=='__main__':main()
