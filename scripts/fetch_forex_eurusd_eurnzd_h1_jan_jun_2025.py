#!/usr/bin/env python3
import json,os,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
PAIRS=['EURUSD','EURNZD'];OUT='data/provider_snapshots/forex_eurusd_eurnzd_h1_jan_jun_2025.json'
def main():
 key=os.environ.get('TWELVEDATA_API_KEY','').strip()
 if not key:raise RuntimeError('TWELVEDATA_API_KEY missing')
 qs=urllib.parse.urlencode({'symbol':','.join(f'{p[:3]}/{p[3:]}' for p in PAIRS),'interval':'1h','outputsize':5000,'start_date':'2025-01-01 00:00:00','end_date':'2025-06-30 23:59:59','timezone':'UTC','order':'asc','apikey':key})
 req=urllib.request.Request('https://api.twelvedata.com/time_series?'+qs,headers={'User-Agent':'trading-api-special2/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:d=json.loads(r.read().decode())
 data={};diag={}
 for p in PAIRS:
  key1=f'{p[:3]}/{p[3:]}';q=d.get(key1) or d.get(p) or {}
  if 'data' in q and isinstance(q['data'],dict):q=q['data']
  vals=q.get('values') or []
  z=sorted([[x['datetime'],float(x['open']),float(x['high']),float(x['low']),float(x['close'])] for x in vals])
  if len(z)<3000:raise RuntimeError(f'{p} insufficient {len(z)} keys={list(d)[:5]}')
  data[p]=z;diag[p]={'bars':len(z),'first':z[0][0],'last':z[-1][0]}
 doc={'version':'FOREX_EURUSD_EURNZD_H1_JAN_JUN_2025_V1','provider':'Twelve Data','coverageCount':2,'pairs':PAIRS,'fetchedAt':datetime.now(timezone.utc).isoformat(),'independentBlock':True,'diagnostics':diag,'data':data};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'status':'OK','diagnostics':diag},indent=2))
if __name__=='__main__':main()
