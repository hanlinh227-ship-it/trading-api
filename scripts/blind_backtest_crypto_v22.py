#!/usr/bin/env python3
import json, math, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as core

# V22 is locked before these outcomes are read. Both dates were not used by V18-V21.
CUTOFFS=[('BLIND_JUL12','2026-07-12T12:00:00Z'),('BLIND_JUL10','2026-07-10T12:00:00Z')]
OBSERVE_MS=5*60_000
HOURS=96
LOOKBACK=48
STOP_FACTOR=.75
FLOW_PAGES=5
FLOW_LIMIT=100
FLOW_SLEEP=.11
OKX_TRADES='https://www.okx.com/api/v5/market/history-trades'

def norm(x,s): return max(-2.0,min(2.0,x/s))
def clip(x,a,b): return max(a,min(b,x))

def macro_score(sym,f,model,breadth):
    # Best surviving core from prior blind work: short-horizon time-series momentum + H4/H1 structure.
    s=.80*norm(f['r6'],.01)+1.15*norm(f['r24'],.025)+1.30*norm(f['r72'],.05)+.65*f['st4']+.35*f['st1']+.30*f['emaBias']
    if sym!='BTC': s += .28*norm(f['rs24'],.025)
    # HTF context and breadth stay soft; they may not override price momentum.
    s += .12*clip(model.get('htfScore',0)/3.0,-2,2)
    if breadth>=.72: s+=.20
    elif breadth<=.28: s-=.20
    d=model.get('rangePositionH1',.5)
    # Anti-chase only at extreme H1 location.
    if d>=.94 and s>0: s-=.35
    elif d<=.06 and s<0: s+=.35
    return s

def fast_get(url,timeout=15):
    req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'trading-api-v22/1.0'})
    last=None
    for k in range(4):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                out=json.loads(r.read().decode())
            time.sleep(FLOW_SLEEP)
            return out
        except Exception as e:
            last=e; time.sleep(.8*(k+1))
    raise last

def tradeflow(sym,start_ms,end_ms):
    inst=f'{sym}-USDT'; cursor=end_ms; trades=[]; calls=0
    for _ in range(FLOW_PAGES):
        q=urllib.parse.urlencode({'instId':inst,'type':'2','after':str(cursor),'limit':str(FLOW_LIMIT)})
        d=fast_get(OKX_TRADES+'?'+q); calls+=1
        if d.get('code')!='0': raise RuntimeError(f"OKX trades {inst}: {d.get('code')} {d.get('msg')}")
        page=d.get('data') or []
        if not page: break
        tss=[]
        for x in page:
            try: t=int(x['ts']); tss.append(t)
            except Exception: continue
            if start_ms<=t<end_ms: trades.append(x)
        if not tss or min(tss)<=start_ms: break
        cursor=min(tss)-1
    if not trades:
        return {'available':False,'calls':calls,'n':0,'ofi':0.0,'buyNotional':0.0,'sellNotional':0.0,'spanSec':0.0,'lastPx':None,'lastTs':None}
    # Deduplicate by tradeId because time pagination can overlap at a millisecond boundary.
    uniq={x.get('tradeId',f"{x.get('ts')}-{i}"):x for i,x in enumerate(trades)}
    tr=sorted(uniq.values(),key=lambda x:int(x['ts']))
    buy=sum(float(x['sz'])*float(x['px']) for x in tr if x.get('side')=='buy')
    sell=sum(float(x['sz'])*float(x['px']) for x in tr if x.get('side')=='sell')
    den=buy+sell; first=int(tr[0]['ts']); last=int(tr[-1]['ts'])
    return {'available':len(tr)>=30 and den>0,'calls':calls,'n':len(tr),'ofi':(buy-sell)/den if den else 0.0,'buyNotional':buy,'sellNotional':sell,'spanSec':round((last-first)/1000,3),'lastPx':float(tr[-1]['px']),'lastTs':last}

def micro_score(flow,pre_entry,atr):
    if not flow.get('available') or not flow.get('lastPx') or not atr: return 0.0,0.0
    ofi=clip(flow['ofi'],-.95,.95)
    move=(flow['lastPx']-pre_entry)/atr
    flow_term=math.tanh(2.0*ofi)
    same=(flow_term==0 or move==0 or flow_term*move>0)
    # Order flow is confirmation, not the primary directional engine.
    score=(1.15*flow_term+.30*clip(move,-1.5,1.5)) if same else (.65*flow_term+.12*clip(move,-1.5,1.5))
    reliability=min(1.0,flow.get('n',0)/200.0)
    return score*reliability,move

def side_rr(macro,micro,flow,move,model):
    score=macro+micro
    side='BUY' if score>=0 else 'SELL'; sgn=1 if side=='BUY' else -1
    macro_aligned=macro*sgn>0; flow_aligned=micro*sgn>0
    ofi=abs(flow.get('ofi') or 0)
    # Raise RR only when the price core and actual aggressor flow agree.
    if macro_aligned and flow_aligned and abs(macro)>=3.0 and ofi>=.38 and abs(move)>=.20 and model.get('regime')=='trend': rr=2.0
    elif macro_aligned and flow_aligned and abs(score)>=2.4 and ofi>=.16: rr=1.8
    else: rr=1.6
    return side,score,rr

def baseline_side_rr(macro):
    side='BUY' if macro>=0 else 'SELL'
    rr=1.8 if abs(macro)>=3.2 else 1.6
    return side,rr

def future(source,sym,start):
    end=start+HOURS*3600000
    if source.startswith('Bybit'): return v6.bybit_future(sym,start,end)
    out=[];cur=start
    while cur<end:
        nxt=min(end,cur+24*3600000)
        out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def evaluate(side,en,sl,tp,cs):
    for i,x in enumerate(cs,1):
        if side=='BUY': hs=x['low']<=sl; ht=x['high']>=tp
        else: hs=x['high']>=sl; ht=x['low']<=tp
        if hs and ht:return {'result':'AMBIGUOUS','candles':i}
        if hs:return {'result':'SL','candles':i}
        if ht:return {'result':'TP','candles':i}
    return {'result':'UNRESOLVED','candles':len(cs)}

def levels(sym,side,en,su,fr,rr):
    atr=su['M15'].get('atr14') or en*.01;base=v6.profile(sym)['stopBase'];recent=fr['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*atr
    if side=='BUY': struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
    else: struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
    return sl,tp,risk

def summarize(rows):
    usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[x for x in resolved if x['outcome']['result']=='TP'];loss=[x for x in resolved if x['outcome']['result']=='SL']
    total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    return {'marketTrades':len(usable),'resolved':len(resolved),'wins':len(wins),'losses':len(loss),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}

def run(label,cutoff):
    cut=v6.iso_ms(cutoff);entry_t=cut+OBSERVE_MS
    bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errors=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            f=core.features(sym,fr,su,bf);tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'model':model,'f':f,'pre':fr['M5'][-1]['close']})
        except Exception as e: errors.append({'symbol':sym+'USDT','error':str(e)})
    breadth=sum(x['f']['r24']>0 for x in tmp)/len(tmp) if tmp else .5
    flow_rows=[];base_rows=[];coverage=0
    for r in tmp:
        sym=r['sym'];macro=macro_score(sym,r['f'],r['model'],breadth)
        try: fl=tradeflow(sym,cut,entry_t)
        except Exception as e: fl={'available':False,'n':0,'ofi':0.0,'lastPx':None,'error':str(e)}
        if fl.get('available'): coverage+=1
        # Market entry after observing the first 5 minutes of the quarter-hour. If public flow is unavailable,
        # use the first post-cutoff 5m close as the observable entry price and set microflow to zero.
        fut_pre=future(r['source'],sym,cut)
        obs=[x for x in fut_pre if x['ts']<entry_t]
        fallback_px=obs[-1]['close'] if obs else r['pre']
        en=fl.get('lastPx') if fl.get('lastPx') is not None else fallback_px
        micro,move=micro_score(fl,r['pre'],r['su']['M15'].get('atr14'))
        side,score,rr=side_rr(macro,micro,fl,move,r['model']);sl,tp,risk=levels(sym,side,en,r['su'],r['fr'],rr);out=evaluate(side,en,sl,tp,future(r['source'],sym,entry_t))
        flow_rows.append({'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':True,'decision':side,'macroScore':round(macro,3),'microScore':round(micro,3),'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'risk':risk,'plannedRR':rr,'breadth':round(breadth,3),'flow':fl,'microMoveATR':round(move,3),'model':r['model'],'features':r['f'],'outcome':out})
        bside,brr=baseline_side_rr(macro);bsl,btp,brisk=levels(sym,bside,en,r['su'],r['fr'],brr);bout=evaluate(bside,en,bsl,btp,future(r['source'],sym,entry_t))
        base_rows.append({'symbol':sym+'USDT','cutoff':cutoff,'entryTimeMs':entry_t,'blind':True,'decision':bside,'macroScore':round(macro,3),'entry':en,'sl':bsl,'tp':btp,'risk':brisk,'plannedRR':brr,'outcome':bout})
    return {'label':label,'cutoff':cutoff,'isTrueBlind':True,'breadth':round(breadth,3),'flowCoverage':round(coverage/len(tmp),3) if tmp else 0,'dataErrors':errors,'baseline':{'summary':summarize(base_rows),'tests':base_rows},'v22':{'summary':summarize(flow_rows),'tests':flow_rows}}

def main():
    samples={n:run(n,c) for n,c in CUTOFFS}
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V22 locked true blind: strongest surviving short-horizon price core (6h/24h/72h momentum + H4/H1 structure + H4 EMA + BTC-relative strength) remains primary; observe only first 5 minutes after quarter-hour, then use up to last 500 OKX public taker trades in that opening window as event-time order-flow imbalance confirmation; enter MARKET at observable +5m price; structural 48xM15 SL with .75 profile ATR floor; RR 1.6 base, 1.8 on macro+flow agreement, 2.0 only strong aligned trend. Baseline uses same +5m entry and no flow. Both blind dates locked before outcomes.','samples':samples}
    with open('data/blind_backtest_v22.json','w') as f: json.dump(payload,f,indent=2)
    print(json.dumps({k:{'baseline':v['baseline']['summary'],'v22':v['v22']['summary'],'flowCoverage':v['flowCoverage']} for k,v in samples.items()},indent=2))

if __name__=='__main__': main()
