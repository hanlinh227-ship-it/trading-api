#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE='https://www.okx.com/api/v5/market/history-trades'
TESTS=[
    ('BTC-USDT','2026-08-12T12:00:00Z'),
    ('SOL-USDT','2026-08-12T12:00:00Z'),
    ('ETH-USDT','2026-08-12T12:00:00Z'),
]

def ms(iso):
    return int(datetime.fromisoformat(iso.replace('Z','+00:00')).timestamp()*1000)

def get(params):
    url=BASE+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v22-probe/1.0'})
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode())

def probe(inst,cutoff):
    cut=ms(cutoff);end=cut+5*60_000
    out={'instId':inst,'cutoff':cutoff,'windowStartMs':cut,'windowEndMs':end,'calls':[],'trades':[]}
    cursor=end
    for i in range(5):
        p={'instId':inst,'type':'2','after':str(cursor),'limit':'100'}
        raw=get(p);data=raw.get('data') or []
        ts=[int(x['ts']) for x in data if x.get('ts')]
        out['calls'].append({'page':i+1,'code':raw.get('code'),'msg':raw.get('msg'),'n':len(data),'minTs':min(ts) if ts else None,'maxTs':max(ts) if ts else None})
        for x in data:
            t=int(x['ts'])
            if cut <= t < end:
                out['trades'].append(x)
        if not ts or min(ts) <= cut:
            break
        cursor=min(ts)-1
    tr=out['trades']
    buy=sum(float(x['sz'])*float(x['px']) for x in tr if x.get('side')=='buy')
    sell=sum(float(x['sz'])*float(x['px']) for x in tr if x.get('side')=='sell')
    den=buy+sell
    out['summary']={'n':len(tr),'buyNotional':buy,'sellNotional':sell,'ofi':(buy-sell)/den if den else None,'firstTs':min((int(x['ts']) for x in tr),default=None),'lastTs':max((int(x['ts']) for x in tr),default=None),'lastPx':float(sorted(tr,key=lambda x:int(x['ts']))[-1]['px']) if tr else None}
    return out

def main():
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'results':[]}
    for inst,c in TESTS:
        try: payload['results'].append(probe(inst,c))
        except Exception as e: payload['results'].append({'instId':inst,'cutoff':c,'error':repr(e)})
    with open('data/okx_tradeflow_probe.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps(payload,indent=2))

if __name__=='__main__': main()
