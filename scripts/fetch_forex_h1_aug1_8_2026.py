#!/usr/bin/env python3
import json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAIRS=[
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
START_DATE="2026-08-01 00:00:00"
END_DATE="2026-08-08 23:59:59"  # Aug 8 is outcome-only buffer; signal holdout is Aug 3-7.
OUT="data/provider_snapshots/forex_h1_aug1_8_2026_final1.json"


def parse_batch(payload):
    out={}
    if isinstance(payload,dict) and 'values' in payload:
        meta=payload.get('meta') or {};s=str(meta.get('symbol') or '').replace('/','').upper()
        if s:out[s]=payload
        return out
    if isinstance(payload,dict):
        for k,v in payload.items():
            if not isinstance(v,dict):continue
            q=v.get('data') if isinstance(v.get('data'),dict) else v
            if isinstance(q,dict) and isinstance(q.get('values'),list):
                meta=q.get('meta') or {};s=str(meta.get('symbol') or k).replace('/','').upper();out[s]=q
    return out


def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'trading-api-final-holdout/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as r:return json.loads(r.read().decode())


def main():
    key=os.environ.get('TWELVEDATA_API_KEY','').strip()
    if not key:raise RuntimeError('TWELVEDATA_API_KEY missing')
    data={};diag={};groups=[PAIRS[i:i+7] for i in range(0,28,7)]
    for bi,g in enumerate(groups):
        syms=','.join(f'{p[:3]}/{p[3:]}' for p in g)
        qs=urllib.parse.urlencode({'symbol':syms,'interval':'1h','outputsize':300,'start_date':START_DATE,'end_date':END_DATE,'timezone':'UTC','order':'asc','apikey':key})
        d=get('https://api.twelvedata.com/time_series?'+qs);got=parse_batch(d)
        miss=[p for p in g if p not in got]
        if miss:raise RuntimeError(f'batch missing {miss}: {str(d)[:800]}')
        for p in g:
            vals=[]
            for x in got[p].get('values') or []:
                try:vals.append([x['datetime'],float(x['open']),float(x['high']),float(x['low']),float(x['close'])])
                except Exception:pass
            vals.sort(key=lambda x:x[0])
            if len(vals)<80:raise RuntimeError(f'{p} too few final rows {len(vals)}')
            data[p]=vals;diag[p]={'bars':len(vals),'first':vals[0][0],'last':vals[-1][0]}
        print('FINAL1_BATCH',bi+1,'OK',','.join(g),flush=True)
        if bi<3:time.sleep(66)
    if set(data)!=set(PAIRS):raise RuntimeError('not 28/28')
    doc={'version':'FOREX_H1_AUG1_8_FINAL1_V1','provider':'Twelve Data','signalHoldout':'2026-08-03..2026-08-07','outcomeBufferThrough':'2026-08-08','coverageCount':28,'requestedPairs':PAIRS,'fetchedAt':datetime.now(timezone.utc).isoformat(),'diagnostics':diag,'data':data}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(doc,open(OUT,'w'),separators=(',',':'))
    print(json.dumps({'status':'OK','path':OUT,'coverage':28,'signalHoldout':doc['signalHoldout']},indent=2),flush=True)
if __name__=='__main__':main()
