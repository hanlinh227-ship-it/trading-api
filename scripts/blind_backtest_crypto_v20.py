#!/usr/bin/env python3
import json, os, sys, itertools
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core

# Development timestamps are already observed in previous experiments.
DEV=[('DEV_JUL30','2026-07-30T12:00:00Z'),('DEV_JUL28','2026-07-28T12:00:00Z'),('DEV_JUL26','2026-07-26T12:00:00Z')]
# These two timestamps are untouched; they are loaded ONLY after the policy is selected on DEV.
FRESH=[('BLIND_JUL24','2026-07-24T12:00:00Z'),('BLIND_JUL22','2026-07-22T12:00:00Z')]
HOURS=96;LOOKBACK=48;STOP_FACTOR=.75
POLICIES=['baseline','fade_all','fade_alt','fade_position','fade_weak']
LOWS=[.05,.10,.15];HIGHS=[.80,.85,.90]

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def outcome(side,en,sl,tp,cs):
    for x in cs:
        if side=='BUY':hs=x['low']<=sl;ht=x['high']>=tp
        else:hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return 'AMB'
        if hs:return 'SL'
        if ht:return 'TP'
    return 'UNR'

def load(cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);_,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm);f=core.features(sym,fr,su,bf);fake={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0};sc=core.score_trade(sym,f,su,fake,.5)
            rows.append({'sym':sym,'source':source,'fr':fr,'su':su,'en':fr['M5'][-1]['close'],'model':model,'f':f,'baseScore':sc,'future':future(source,sym,cut)})
        except Exception:pass
    breadth=sum(r['f']['r24']>0 for r in rows)/len(rows) if rows else .5
    # Recompute soft-breadth score consistently with the known breadth.
    for r in rows:
        fake={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0};r['baseScore']=core.score_trade(r['sym'],r['f'],r['su'],fake,breadth)
    return rows,breadth

def choose(r,breadth,policy,lo,hi):
    base='BUY' if r['baseScore']>=0 else 'SELL';ext_low=breadth<=lo;ext_high=breadth>=hi;pos=r['model'].get('rangePositionH1',.5);strong=abs(r['baseScore'])>=4.5
    side=base;fade=False
    if policy=='fade_all':
        if ext_low:side='BUY';fade=(side!=base)
        elif ext_high:side='SELL';fade=(side!=base)
    elif policy=='fade_alt' and r['sym'] not in v6.MAJORS:
        if ext_low:side='BUY';fade=(side!=base)
        elif ext_high:side='SELL';fade=(side!=base)
    elif policy=='fade_position':
        if ext_low and pos<=.38:side='BUY';fade=(side!=base)
        elif ext_high and pos>=.62:side='SELL';fade=(side!=base)
    elif policy=='fade_weak':
        if not strong:
            if ext_low:side='BUY';fade=(side!=base)
            elif ext_high:side='SELL';fade=(side!=base)
    return side,fade

def rr_for(r,side,fade):
    sign=1 if side=='BUY' else -1;f=r['f'];align=sum(x*sign>0 for x in (f['r6'],f['r24'],f['r72'],f['r7d']));st=sum(x*sign>0 for x in (f['st4'],f['st1']))
    if fade:return 1.50
    if align>=4 and st>=1 and abs(r['baseScore'])>=4.5:return 1.90
    if align>=3 and abs(r['baseScore'])>=2.5:return 1.70
    return 1.50

def trade_result(r,breadth,policy,lo,hi):
    side,fade=choose(r,breadth,policy,lo,hi);rr=rr_for(r,side,fade);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
    if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
    else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
    z=outcome(side,en,sl,tp,r['future']);return side,fade,rr,en,sl,tp,z

def eval_cfg(rows,breadth,p,lo,hi):
    w=l=u=0;total=0;rrs=[]
    for r in rows:
        _,_,rr,_,_,_,z=trade_result(r,breadth,p,lo,hi)
        if z=='TP':w+=1;total+=rr;rrs.append(rr)
        elif z=='SL':l+=1;total-=1;rrs.append(rr)
        else:u+=1
    n=w+l;return {'wins':w,'losses':l,'unresolved':u,'winRate':round(100*w/n,2) if n else None,'avgRR':round(sum(rrs)/n,3) if n else None,'expectancyR':round(total/n,3) if n else None}

def select_policy():
    ds={};
    for n,c in DEV:
        rows,b=load(c);ds[n]=(rows,b)
    grid=[]
    for p,lo,hi in itertools.product(POLICIES,LOWS,HIGHS):
        if p=='baseline' and (lo!=LOWS[0] or hi!=HIGHS[0]):continue
        per={k:eval_cfg(v[0],v[1],p,lo,hi) for k,v in ds.items()};minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgwr=sum(x['winRate'] for x in per.values())/len(per);avgexp=sum(x['expectancyR'] for x in per.values())/len(per);avgrr=sum(x['avgRR'] for x in per.values())/len(per)
        robust=minwr+14*minexp+5*(avgrr-1.5)+.12*avgwr+4*avgexp
        grid.append({'policy':p,'low':lo,'high':hi,'perDev':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgWinRate':round(avgwr,2),'avgRR':round(avgrr,3),'avgExpectancyR':round(avgexp,3),'robustScore':round(robust,3)})
    feasible=[x for x in grid if x['minExpectancyR']>0 and x['minWinRate']>=38 and x['avgRR']>=1.5]
    chosen=max(feasible or grid,key=lambda x:x['robustScore'])
    return chosen,sorted(grid,key=lambda x:x['robustScore'],reverse=True)[:15]

def fresh_run(label,cutoff,cfg):
    rows,b=load(cutoff);details=[]
    for r in rows:
        side,fade,rr,en,sl,tp,z=trade_result(r,b,cfg['policy'],cfg['low'],cfg['high']);details.append({'symbol':r['sym']+'USDT','cutoff':cutoff,'blind':True,'decision':side,'fadeBreadth':fade,'score':round(r['baseScore'],3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(b,3),'model':r['model'],'features':r['f'],'outcome':{'result':z}})
    resolved=[x for x in details if x['outcome']['result'] in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':True,'marketTrades':len(details),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(details)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(b,3),'breadthFades':sum(x['fadeBreadth'] for x in details)}
    return {'summary':s,'tests':details}

def main():
    chosen,top=select_policy()
    # Critical blind boundary: fresh data is loaded only after chosen is fixed above.
    fresh={n:fresh_run(n,c,chosen) for n,c in FRESH}
    p={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V20 walk-forward: select breadth-regime switch only on already-seen Jul30/Jul28/Jul26; then lock and test untouched Jul24/Jul22. Direction core = V17 short multi-horizon momentum/structure. Extreme market breadth may switch to contrarian only under selected policy. 48 M15 structural SL + .75 profile ATR floor; RR1.5/1.7/1.9 by alignment; no WAIT/LIMIT.','development':{'chosen':chosen,'top':top},'fresh':fresh}
    with open('data/blind_backtest_v20.json','w') as f:json.dump(p,f,indent=2)
    print(json.dumps({'chosen':chosen,'fresh':{k:v['summary'] for k,v in fresh.items()}},indent=2))
if __name__=='__main__':main()
