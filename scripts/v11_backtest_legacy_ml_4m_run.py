#!/usr/bin/env python3
"""Runtime repair layer for V11 legacy-learned backtest.

Keeps the main research engine stable while fixing provider/runtime specifics:
- correct enumerate() construction for enriched-row timestamp maps;
- Crypto historical source fanout: KuCoin -> Gate.io -> OKX, all exact USDT spot;
- robust missing-symbol handling in cross-crypto regime construction.
"""
from __future__ import annotations
import importlib.util, json, time, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'scripts/v11_backtest_legacy_ml_4m.py'
spec=importlib.util.spec_from_file_location('v11legacy',P)
b=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(b)


def jget(url,timeout=35,retries=4):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v11-backtest/1.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last=e;time.sleep(.35*(n+1))
    raise RuntimeError(f'HTTP_FAIL {last}')


def base_asset(symbol):
    s=b.norm(symbol)
    if not s.endswith('USDT'):raise ValueError(s)
    return s[:-4]


def kucoin_4h(symbol,start_ts,end_ts):
    inst=base_asset(symbol)+'-USDT';out=[];cur=start_ts;span=1450*14400
    while cur<=end_ts:
        z=min(end_ts,cur+span)
        q=urllib.parse.urlencode({'type':'4hour','symbol':inst,'startAt':cur,'endAt':z})
        j=jget('https://api.kucoin.com/api/v1/market/candles?'+q)
        if str(j.get('code'))!='200000':raise RuntimeError(j.get('msg') or j)
        arr=j.get('data') or []
        if not arr and not out:raise RuntimeError('KUCOIN_EMPTY')
        for x in arr:
            if len(x)<6:continue
            t=int(x[0]);out.append([t,float(x[1]),float(x[3]),float(x[4]),float(x[2]),float(x[5])])
        cur=z+1;time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('KUCOIN_EMPTY')
    return [d[k] for k in sorted(d)],'KuCoin Spot 4H',True


def gate_4h(symbol,start_ts,end_ts):
    pair=base_asset(symbol)+'_USDT';out=[];cur=start_ts;span=950*14400
    while cur<=end_ts:
        z=min(end_ts,cur+span)
        q=urllib.parse.urlencode({'currency_pair':pair,'interval':'4h','from':cur,'to':z,'limit':'1000'})
        arr=jget('https://api.gateio.ws/api/v4/spot/candlesticks?'+q)
        if isinstance(arr,dict):raise RuntimeError(arr.get('message') or arr)
        if not arr and not out:raise RuntimeError('GATE_EMPTY')
        for x in arr:
            if len(x)<6:continue
            t=int(float(x[0]));vol=float(x[6]) if len(x)>6 else float(x[1] or 0)
            out.append([t,float(x[5]),float(x[3]),float(x[4]),float(x[2]),vol])
        cur=z+1;time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('GATE_EMPTY')
    return [d[k] for k in sorted(d)],'Gate.io Spot 4H',True


def okx_4h(symbol,start_ts,end_ts):
    inst=base_asset(symbol)+'-USDT';out=[];after=None;guard=0
    while guard<30:
        guard+=1;params={'instId':inst,'bar':'4H','limit':'100'}
        if after is not None:params['after']=str(after)
        q=urllib.parse.urlencode(params);j=jget('https://www.okx.com/api/v5/market/history-candles?'+q)
        if str(j.get('code'))!='0':raise RuntimeError(j.get('msg') or j)
        arr=j.get('data') or []
        if not arr:break
        ts=[]
        for x in arr:
            if len(x)<6:continue
            t=int(x[0])//1000;ts.append(t);out.append([t,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        oldest=min(ts)
        if oldest<=start_ts:break
        nxt=oldest*1000
        if after==nxt:break
        after=nxt;time.sleep(.06)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d:raise RuntimeError('OKX_EMPTY')
    return [d[k] for k in sorted(d)],'OKX Spot 4H',True


_original_fetch=b.fetch_one

def fetch_one(symbol,market,start_ts,end_ts):
    if market!='crypto':return _original_fetch(symbol,market,start_ts,end_ts)
    errors=[]
    for fn in (kucoin_4h,gate_4h,okx_4h):
        try:
            rows,src,exact=fn(symbol,start_ts,end_ts)
            # Need enough pre-evaluation history for the ML model, not just a few listing bars.
            if len(rows)<900:raise RuntimeError(f'{src} insufficient4h={len(rows)}')
            return symbol,rows,src,exact,None
        except Exception as e:errors.append(f'{fn.__name__}:{e}')
    return symbol,[],None,False,' | '.join(errors)[:900]


def forex_maps(data):
    maps={s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
    if not maps:return {},[]
    common=set.intersection(*(set(x) for x in maps.values()))
    return maps,sorted(t for t in common if t.hour in (0,4,8,12,16,20))


def crypto_regime(symbols,maps,t):
    eligible={}
    for s in symbols:
        q=maps.get(s,{}).get(t)
        if q and q[1].get('ret24') is not None and q[1].get('adx') is not None:eligible[s]=q
    if len(eligible)<max(15,int(len(symbols)*.5)):return None
    import statistics
    rets=[q[1]['ret24'] for q in eligible.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);disp=statistics.pstdev(rets) or 1e-9
    btc=eligible.get('BTCUSDT');btc24=btc[1]['ret24'] if btc else med;btc72=btc[1].get('ret72',0) if btc else 0
    return eligible,{'breadth':breadth,'median24':med,'dispersion24':disp,'btc24':btc24,'btc72':btc72,'eligible':len(eligible)}


def build_crypto_raw(symbols,data):
    maps={s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
    times=sorted(set().union(*(set(x) for x in maps.values()))) if maps else []
    raw={s:[] for s in symbols};baseline=(1.0,1.0,5)
    for t in times:
        regpack=crypto_regime(symbols,maps,t)
        if not regpack:continue
        eligible,reg=regpack
        for s,q in eligible.items():
            i,row=q
            for side in (1,-1):
                o=b.exec_intraday(data[s],i,side,baseline,'crypto')
                if o:raw[s].append({'i':i,'time':t,'day':b.daystr(t),'side':side,'x':b.crypto_feature(s,row,reg,side),'label':1 if o[0]=='TP' else 0})
    return raw


def build_generic_raw(symbols,data,market):
    import statistics
    maps={s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
    raw={s:[] for s in symbols};baseline=(1.0,1.0,8);times=sorted(set().union(*(set(x) for x in maps.values()))) if maps else []
    for t in times:
        avail=[]
        for s in symbols:
            q=maps.get(s,{}).get(t)
            if q and q[1].get('ret24') is not None:avail.append((s,q))
        vals=[q[1]['ret24'] for _,q in avail];med=statistics.median(vals) if vals else 0;disp=statistics.pstdev(vals) if len(vals)>1 else 0
        for s,q in avail:
            i,row=q
            if row.get('adx') is None or row.get('rsi') is None:continue
            rel=(row.get('ret24',0)-med)/(disp or 1)
            for side in (1,-1):
                o=b.exec_intraday(data[s],i,side,baseline,market)
                if o:raw[s].append({'i':i,'time':t,'day':b.daystr(t),'side':side,'x':b.generic_feature(data[s],i,side,(side*rel,abs(med)*20,disp*20)),'label':1 if o[0]=='TP' else 0})
    return raw

b.fetch_one=fetch_one
b.forex_maps=forex_maps
b.crypto_regime=crypto_regime
b.build_crypto_raw=build_crypto_raw
b.build_generic_raw=build_generic_raw

if __name__=='__main__':raise SystemExit(b.main())
