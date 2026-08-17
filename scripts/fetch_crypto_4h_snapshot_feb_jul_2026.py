#!/usr/bin/env python3
import json, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS='BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC'.split()
GATE={'POPCAT','FARTCOIN'}
KRAKEN={'TON','IP'}
OKX=[s for s in SYMBOLS if s not in GATE|KRAKEN]
START=int(datetime(2026,2,1,tzinfo=timezone.utc).timestamp())
END=int(datetime(2026,8,1,tzinfo=timezone.utc).timestamp())-1
OUT='data/provider_snapshots/crypto_4h_feb_jul_2026.json'
UA='trading-api-crypto-snapshot/1.0'


def get_json(url, retries=5, timeout=20):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last=e;time.sleep(.7*(n+1))
    raise RuntimeError(str(last))


def okx_symbol(sym):
    inst=f'{sym}-USDT';cursor=END*1000;ded={};pages=0
    while cursor>=START*1000 and pages<30:
        qs=urllib.parse.urlencode({'instId':inst,'bar':'4H','after':str(cursor),'limit':'100'})
        d=get_json('https://www.okx.com/api/v5/market/history-candles?'+qs)
        if d.get('code')!='0':raise RuntimeError(f"OKX {sym} {d.get('code')} {d.get('msg')}")
        rows=d.get('data') or []
        if not rows:break
        oldest=None
        for x in rows:
            ts=int(x[0])//1000
            if START<=ts<=END:
                ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
            oldest=ts if oldest is None else min(oldest,ts)
        if oldest is None or oldest*1000>=cursor:break
        cursor=oldest*1000-1;pages+=1;time.sleep(.16)
        if oldest<START:break
    rows=[ded[k] for k in sorted(ded)]
    return rows,'OKX',pages


def gate_symbol(sym):
    pair=f'{sym}_USDT';ded={};chunk=950*4*3600;cur=START;pages=0
    while cur<=END:
        to=min(END,cur+chunk)
        qs=urllib.parse.urlencode({'currency_pair':pair,'interval':'4h','from':cur,'to':to,'limit':'1000'})
        d=get_json('https://api.gateio.ws/api/v4/spot/candlesticks?'+qs)
        if isinstance(d,dict) and d.get('label'):raise RuntimeError(f"GATE {sym} {d}")
        for x in d or []:
            ts=int(x[0])
            if START<=ts<=END:
                # Gate: timestamp, quote_volume, close, high, low, open, base_volume, closed
                ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[5]),float(x[3]),float(x[4]),float(x[2])]
        cur=to+1;pages+=1;time.sleep(.25)
    return [ded[k] for k in sorted(ded)],'GATE',pages


def kraken_symbol(sym):
    pair=f'{sym}USD';ded={};since=START;pages=0
    while since<=END and pages<5:
        qs=urllib.parse.urlencode({'pair':pair,'interval':'240','since':since})
        d=get_json('https://api.kraken.com/0/public/OHLC?'+qs)
        if d.get('error'):raise RuntimeError(f"KRAKEN {sym} {d.get('error')}")
        result=d.get('result') or {};key=next((k for k in result if k!='last'),None)
        rows=result.get(key) or []
        if not rows:break
        last_ts=since
        for x in rows:
            ts=int(x[0]);last_ts=max(last_ts,ts)
            if START<=ts<=END:
                ded[ts]=[datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),float(x[1]),float(x[2]),float(x[3]),float(x[4])]
        nxt=int(result.get('last') or (last_ts+4*3600))
        if nxt<=since:nxt=last_ts+4*3600
        since=nxt;pages+=1;time.sleep(.35)
        if last_ts>END:break
    return [ded[k] for k in sorted(ded)],'KRAKEN',pages


def fetch_one(sym):
    if sym in GATE:return sym,*gate_symbol(sym)
    if sym in KRAKEN:return sym,*kraken_symbol(sym)
    return sym,*okx_symbol(sym)


def main():
    results={};diag={};errors={}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures={ex.submit(fetch_one,s):s for s in SYMBOLS}
        for fut in as_completed(futures):
            s=futures[fut]
            try:
                sym,rows,src,pages=fut.result()
                if len(rows)<24:raise RuntimeError(f'too few bars {len(rows)}')
                if rows[-1][0][:10]<'2026-07-28':raise RuntimeError(f'stale last {rows[-1][0]}')
                results[sym]=rows;diag[sym]={'source':src,'bars':len(rows),'first':rows[0][0],'last':rows[-1][0],'pages':pages}
                print('CRYPTO_SNAPSHOT',sym,src,len(rows),rows[0][0],rows[-1][0],flush=True)
            except Exception as e:
                errors[s]=str(e);print('CRYPTO_FAIL',s,str(e),flush=True)
    if errors or set(results)!=set(SYMBOLS):
        raise RuntimeError('61-symbol coverage failed: '+json.dumps(errors))
    doc={'version':'CRYPTO_4H_SNAPSHOT_FEB_JUL_2026_V1','interval':'4h','requestedSymbols':SYMBOLS,'coverageCount':len(results),'startDate':'2026-02-01','endDate':'2026-07-31','hiddenFinalHoldoutNotIncluded':'2026-08-01 onward','sources':{'OKX':len([s for s in SYMBOLS if diag[s]['source']=='OKX']),'GATE':len([s for s in SYMBOLS if diag[s]['source']=='GATE']),'KRAKEN':len([s for s in SYMBOLS if diag[s]['source']=='KRAKEN'])},'diagnostics':diag,'data':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True)
    with open(OUT,'w',encoding='utf-8') as f:json.dump(doc,f,separators=(',',':'))
    print(json.dumps({'status':'OK','path':OUT,'coverage':len(results),'sources':doc['sources'],'totalBars':sum(x['bars'] for x in diag.values()),'hiddenAugustNotIncluded':True},indent=2),flush=True)

if __name__=='__main__':main()
