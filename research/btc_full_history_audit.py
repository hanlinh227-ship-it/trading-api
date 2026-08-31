#!/usr/bin/env python3
import csv, io, urllib.request
from datetime import datetime, timezone
URL='https://raw.githubusercontent.com/simom1/XAUUSD-history/main/Crypto/BTCUSD/BTCUSD_M5.csv'

def load_full():
    req=urllib.request.Request(URL,headers={'User-Agent':'btc-full-history-audit'})
    with urllib.request.urlopen(req,timeout=180) as r:
        text=r.read().decode('utf-8-sig')
    rows=[]; bad=0
    for x in csv.DictReader(io.StringIO(text)):
        try:
            raw=(x.get('time') or x.get('datetime')).strip().replace('T',' ').replace('Z','')[:19]
            d=datetime.strptime(raw,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            rows.append((int(d.timestamp()),raw,float(x['open']),float(x['high']),float(x['low']),float(x['close'])))
        except Exception:
            bad+=1
    rows.sort(key=lambda z:z[0])
    return rows,bad

def main():
    rows,bad=load_full()
    print('=== BTCUSD M5 FULL HISTORY AUDIT ===')
    print('SOURCE',URL)
    print('ROWS',len(rows),'BAD_ROWS',bad)
    if not rows:return
    print('RANGE',rows[0][1],'->',rows[-1][1])
    dup=0; backward=0; gaps=[]
    prev=rows[0][0]
    for r in rows[1:]:
        dt=r[0]-prev
        if dt==0:dup+=1
        elif dt<0:backward+=1
        elif dt!=300:gaps.append((prev,r[0],dt))
        prev=r[0]
    missing=sum(max(0,g[2]//300-1) for g in gaps)
    print('DUPLICATES',dup,'BACKWARD',backward,'GAP_EVENTS',len(gaps),'EST_MISSING_BARS',missing)
    if gaps:
        print('TOP_GAPS')
        for a,b,d in sorted(gaps,key=lambda z:z[2],reverse=True)[:20]:
            print(datetime.fromtimestamp(a,tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),'->',datetime.fromtimestamp(b,tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),'seconds',d,'missing',max(0,d//300-1))
    expected=(rows[-1][0]-rows[0][0])//300+1
    coverage=100*len({r[0] for r in rows})/expected if expected>0 else 0
    print(f'EXPECTED_GRID_BARS={expected} UNIQUE_BARS={len({r[0] for r in rows})} COVERAGE={coverage:.6f}%')
if __name__=='__main__':main()
