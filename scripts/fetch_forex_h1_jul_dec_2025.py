#!/usr/bin/env python3
import json,os,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
PAIRS=["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD","EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY","GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD","AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
START_DATE='2025-07-01 00:00:00';END_DATE='2025-12-31 23:59:59';OUT='data/provider_snapshots/forex_h1_jul_dec_2025.json'
def req(url):
 r=urllib.request.Request(url,headers={'User-Agent':'trading-api-2025-holdout/1.0','Accept':'application/json'})
 with urllib.request.urlopen(r,timeout=120) as f:return json.loads(f.read().decode())
def parse(payload):
 out={}
 if isinstance(payload,dict) and 'values' in payload:
  s=str((payload.get('meta') or {}).get('symbol') or '').replace('/','').upper();out[s]=payload;return out
 for k,v in (payload.items() if isinstance(payload,dict) else []):
  q=v.get('data') if isinstance(v,dict) and isinstance(v.get('data'),dict) else v
  if isinstance(q,dict) and isinstance(q.get('values'),list):out[str((q.get('meta') or {}).get('symbol') or k).replace('/','').upper()]=q
 return out
def compact(v):
 z=[]
 for r in v:
  try:z.append([r['datetime'],float(r['open']),float(r['high']),float(r['low']),float(r['close'])])
  except:pass
 return sorted(z)
def main():
 key=os.environ.get('TWELVEDATA_API_KEY','').strip()
 if not key:raise RuntimeError('TWELVEDATA_API_KEY missing')
 data={};diag={};groups=[PAIRS[i:i+7] for i in range(0,28,7)]
 for n,g in enumerate(groups):
  qs=urllib.parse.urlencode({'symbol':','.join(f'{p[:3]}/{p[3:]}' for p in g),'interval':'1h','outputsize':5000,'start_date':START_DATE,'end_date':END_DATE,'timezone':'UTC','order':'asc','apikey':key});got=parse(req('https://api.twelvedata.com/time_series?'+qs));missing=[p for p in g if p not in got]
  if missing:raise RuntimeError(f'missing {missing}')
  for p in g:
   z=compact(got[p].get('values') or [])
   if len(z)<1500:raise RuntimeError(f'{p} rows {len(z)}')
   data[p]=z;diag[p]={'bars':len(z),'first':z[0][0],'last':z[-1][0]}
  print('BATCH',n+1,'OK',flush=True)
  if n<3:time.sleep(66)
 doc={'version':'FOREX_H1_JUL_DEC_2025_V1','provider':'Twelve Data','interval':'1h','coverageCount':len(data),'requestedPairs':PAIRS,'startDate':START_DATE,'endDate':END_DATE,'fetchedAt':datetime.now(timezone.utc).isoformat(),'independentFrom2026MethodDesign':True,'diagnostics':diag,'data':data};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'));print(json.dumps({'status':'OK','coverage':len(data),'totalBars':sum(x['bars'] for x in diag.values())},indent=2),flush=True)
if __name__=='__main__':main()
