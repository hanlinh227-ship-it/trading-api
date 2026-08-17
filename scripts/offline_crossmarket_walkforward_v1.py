#!/usr/bin/env python3
import json, os, re, statistics
from collections import defaultdict

FILES={
  'FOREX':[
    'data/blind_backtest_forex_f4.json','data/blind_backtest_forex_f5_horizon.json',
    'data/blind_backtest_forex_f6.json','data/blind_backtest_forex_f6_dual_horizon.json'],
  'CRYPTO':[
    'data/blind_backtest_v24_validation.json','data/blind_backtest_v26.json',
    'data/blind_backtest_v27_final.json','data/final_market_vs_limit_blind.json']
}
ISO=re.compile(r'20\d\d-\d\d-\d\d')

def first_date(*xs):
    for x in xs:
        if isinstance(x,str):
            m=ISO.search(x)
            if m:return m.group(0)
    return None

def outcome_obj(x):
    if not isinstance(x,dict): return None
    o=x.get('outcome')
    if isinstance(o,dict): return o.get('result') or o.get('status')
    if isinstance(o,str): return o
    return x.get('result') if isinstance(x.get('result'),str) else None

def rr_of(m):
    if not isinstance(m,dict):return None
    for k in ('rr','plannedRR','effectiveRR','avgPlannedRR','avgRR'):
        v=m.get(k)
        if isinstance(v,(int,float)):return float(v)
    return None

def r_value(m, is_limit=False):
    if not isinstance(m,dict):return None
    res=(outcome_obj(m) or m.get('status') or '').upper()
    if res in ('TP','WIN','TARGET'): return rr_of(m) or 1.0
    if res in ('SL','LOSS','STOP'): return -1.0
    if is_limit and (res in ('NO_FILL','NOT_FILLED','TARGET_BEFORE_FILL','CANCELLED') or m.get('filled') is False): return 0.0
    return None

def walk(x, ctx=None):
    ctx=dict(ctx or {})
    if isinstance(x,dict):
        # Never use generatedAt as a trade date. Only genuine historical decision timestamps may set it.
        for k in ('cutoff','signalTime','entryTime','date'):
            if k in x:
                d=first_date(x.get(k))
                if d: ctx['date']=d; break
        sym=x.get('symbol') or x.get('pair')
        if isinstance(sym,str):ctx['symbol']=sym.replace('/','').upper()
        side=x.get('side') or x.get('decision')
        if isinstance(side,str):ctx['side']=side
        if 'symbol' in ctx:
            m=x.get('market')
            if isinstance(m,dict) and (outcome_obj(m) or isinstance(m.get('outcome'),dict)):
                yield ctx,x
            elif outcome_obj(x) and any(k in x for k in ('entry','sl','tp','plannedRR','rr')):
                yield ctx,{'market':x}
        for k,v in x.items():
            c=dict(ctx)
            kd=first_date(str(k))
            if kd:c['date']=kd
            yield from walk(v,c)
    elif isinstance(x,list):
        for v in x:yield from walk(v,ctx)

def load_rows(asset):
    rows=[]; seen=set()
    for fn in FILES[asset]:
        if not os.path.exists(fn):continue
        with open(fn,encoding='utf-8') as f:data=json.load(f)
        for ctx,rec in walk(data):
            sym=ctx.get('symbol'); date=ctx.get('date')
            if not sym or not date:continue
            if asset=='CRYPTO' and not sym.endswith('USDT'): continue
            if asset=='FOREX' and (len(sym)!=6 or sym.endswith('USDT')): continue
            m=rec.get('market') if isinstance(rec.get('market'),dict) else None
            mr=r_value(m)
            if mr is None:continue
            entry=m.get('entry') if isinstance(m,dict) else None
            key=(fn,date,sym,ctx.get('side'),entry,mr)
            if key in seen:continue
            seen.add(key)
            l=rec.get('limit') if isinstance(rec.get('limit'),dict) else None
            lr=r_value(l,True) if l else None
            d24=m.get('direction24hCorrect') if isinstance(m,dict) else None
            d6=m.get('direction6hCorrect') if isinstance(m,dict) else None
            rows.append({'asset':asset,'file':fn,'date':date,'symbol':sym,'marketR':mr,'limitR':lr,
                         'marketRR':rr_of(m),'direction24':d24,'direction6':d6})
    return rows

def summarize(vals):
    vals=[v for v in vals if v is not None]
    if not vals:return {'n':0}
    wins=sum(v>0 for v in vals); losses=sum(v<0 for v in vals); flat=sum(v==0 for v in vals)
    resolved=wins+losses
    return {'n':len(vals),'resolved':resolved,'wins':wins,'losses':losses,'flat':flat,
            'winRateResolved':round(100*wins/resolved,2) if resolved else None,
            'meanR':round(statistics.mean(vals),3),'medianR':round(statistics.median(vals),3)}

def walkforward(rows, min_hist=2):
    dates=sorted(set(r['date'] for r in rows)); hist=defaultdict(list); lhist=defaultdict(list); dhist=defaultdict(list)
    tested=[]; qualified=[]; routed=[]; bydate={}
    for date in dates:
        day=[r for r in rows if r['date']==date]
        qday=[]; rday=[]
        # Freeze eligibility at the start of each blind date so symbols on the same date cannot train each other.
        eligible={}
        route_limit={}
        for sym in {r['symbol'] for r in day}:
            prior=hist[sym]; d=[x for x in dhist[sym] if isinstance(x,bool)]
            qual=False
            if len(prior)>=min_hist:
                mean=statistics.mean(prior); wr=sum(x>0 for x in prior)/max(1,sum(x!=0 for x in prior))
                dacc=sum(d)/len(d) if d else None
                qual=(mean>0.05 and wr>=0.45) or (dacc is not None and dacc>=0.65 and mean>-0.05)
            eligible[sym]=qual
            lp=[x for x in lhist[sym] if x is not None]
            route_limit[sym]=len(lp)>=min_hist and len(prior)>=min_hist and statistics.mean(lp)>statistics.mean(prior)+0.20
        for r in day:
            sym=r['symbol']; tested.append(r['marketR'])
            if eligible.get(sym):
                qday.append(r['marketR']); qualified.append(r['marketR'])
                use_limit=route_limit.get(sym,False)
                rv=(r['limitR'] if use_limit and r['limitR'] is not None else r['marketR'])
                routed.append(rv);rday.append(rv)
        for r in day:
            sym=r['symbol']; hist[sym].append(r['marketR'])
            if r['limitR'] is not None:lhist[sym].append(r['limitR'])
            if isinstance(r['direction24'],bool):dhist[sym].append(r['direction24'])
        bydate[date]={'all':summarize([r['marketR'] for r in day]),'qualifiedMarket':summarize(qday),'qualifiedRouted':summarize(rday)}
    return {'dates':dates,'allMarket':summarize(tested),'qualifiedMarket':summarize(qualified),
            'qualifiedAdaptiveExecution':summarize(routed),'byDate':bydate,
            'rule':{'minPriorResolved':min_hist,'qualification':'prior meanR > +0.05 and WR>=45%, OR prior direction24>=65% with meanR>-0.05','execution':'LIMIT only when prior LIMIT meanR exceeds prior MARKET meanR by >0.20R; else MARKET','sameDateLeakage':False}}

def diagnostics(rows):
    sl=[r for r in rows if r['marketR']<0]
    right24=[r for r in sl if r['direction24'] is True]
    wrong24=[r for r in sl if r['direction24'] is False]
    return {'marketSLWithDirection24Known':len(right24)+len(wrong24),'slBut24hDirectionCorrect':len(right24),
            'slAnd24hDirectionWrong':len(wrong24),
            'pctKnownSLThatWereEntryBarrierErrors':round(100*len(right24)/(len(right24)+len(wrong24)),2) if right24 or wrong24 else None}

def main():
    out={'version':'CROSS-MARKET OFFLINE WALK-FORWARD V1.1','providerCreditsUsed':0,'integrity':{
        'usesOnlyCommittedBlindResults':True,'chronologicalWalkForward':True,'futureBlockNotUsedForQualification':True,
        'sameDateTradesDoNotTrainEachOther':True,'generatedAtNeverUsedAsTradeDate':True,'notAReconstructionOfMissingRawCandles':True}}
    for asset in ('FOREX','CRYPTO'):
        rows=load_rows(asset)
        out[asset]={'rowsRecovered':len(rows),'files':FILES[asset],'walkForward':walkforward(rows),'diagnostics':diagnostics(rows)}
    out['improvements']={
      'shared':['separate bias error from entry/barrier error','structural SL + volatility floor','do not use tiny TP to inflate WR','MARKET default for fresh continuation','LIMIT only with demonstrated pullback advantage','walk-forward reliability gate before live entry'],
      'FOREX':['pair reliability learned only from prior blocks','do not hard-average 3h and 24h horizons','weak pairs require reworked bias before execution tuning'],
      'CRYPTO':['market breadth is context, not a standalone reversal signal','BTC/regime + structure must agree before continuation entry','many 24h-correct SLs imply entry/barrier timing deserves explicit treatment']}
    os.makedirs('data',exist_ok=True)
    with open('data/offline_crossmarket_walkforward_v1.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:out[k] for k in ('FOREX','CRYPTO')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
