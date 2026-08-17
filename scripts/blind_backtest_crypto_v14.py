#!/usr/bin/env python3
import json, os, sys, statistics
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

# Training/regression only. Fresh blind cutoff is added only after this policy is frozen.
CUTOFFS=[
 ('TRAIN_A_2026-08-13_12UTC','2026-08-13T12:00:00Z',False),
 ('TRAIN_B_2026-08-12_12UTC','2026-08-12T12:00:00Z',False),
]
HOURS=120
W={'v6':1.3,'h1_4':.5,'m15':.5,'h1_12':.4,'breadth':.5,'range':.5}

def clamp(x,a=-1,b=1):return max(a,min(b,x))
def sgn(x):return 1 if x>0 else -1 if x<0 else 0

def state_stats(loaded):
    r4=[v6.ret(fr['H1'],4) for _,_,fr,_ in loaded];r12=[v6.ret(fr['H1'],12) for _,_,fr,_ in loaded]
    b4=sum(x>0 for x in r4)/len(r4);b12=sum(x>0 for x in r12)/len(r12)
    disp4=statistics.pstdev(r4) if len(r4)>1 else 0
    med4=statistics.median(r4);med12=statistics.median(r12)
    return {'breadth4h':b4,'breadth12h':b12,'dispersion4h':disp4,'median4h':med4,'median12h':med12}

def direction(sym,fr,su,bf,bm,state):
    base,model=v6.directional_score(sym,su,fr,bf,bm)
    v=sgn(base)*clamp(abs(base)/5,.2,1)
    m4=clamp(v6.ret(fr['H1'],4)/.012);mm=clamp(v6.ret(fr['M15'],4)/.006);m12=clamp(v6.ret(fr['H1'],12)/.025)
    b4,b12=state['breadth4h'],state['breadth12h'];breadth=clamp((b4-.5)/.25);accel=clamp((b4-b12)/.35)
    pos=model['rangePositionH1'];possig=1-2*pos;rg=model['regime'];k4=1.25 if rg=='transition' else 1.0;kr=1.5 if rg=='range' else .35
    score=W['v6']*v+W['h1_4']*k4*m4+W['m15']*mm+W['h1_12']*m12+W['breadth']*(.55*breadth+.45*accel)+W['range']*kr*possig
    if v6.profile(sym)['type'] in ('new_high_beta','alt'):
        score-=.45*W['v6']*v;score+=.35*W['h1_4']*k4*m4+.25*W['m15']*mm
    # If cross-sectional dispersion is extreme, trust individual time-series more than breadth.
    if state['dispersion4h']>.025:
        score-=.25*W['breadth']*(.55*breadth+.45*accel);score+=.20*m4
    if abs(score)<.18:score=.18 if base>=0 else -.18
    model=dict(model);model.update({'v6BaseScore':base,'stateScore':score,'h1Momentum4':m4,'m15Momentum1h':mm,'h1Momentum12':m12,'marketState':state})
    return ('BUY' if score>=0 else 'SELL'),score,model

def rr_target(model,score,profile):
    rg=model['regime'];c=abs(score)
    if rg=='trend':rr=1.75 if c<1.0 else 1.9 if c<1.8 else 2.05
    elif rg=='transition':rr=1.55 if c<1.0 else 1.7 if c<1.8 else 1.85
    else:rr=1.5 if c<1.0 else 1.6 if c<1.8 else 1.7
    if profile in ('new_high_beta','meme') and rg!='trend':rr=max(1.5,rr-.05)
    return rr

def barriers(sym,side,en,su,fr,model,score):
    p=v6.profile(sym);a=su['M15']['atr14'] or en*.01;recent=fr['M15'][-40:]
    floor=1.2*p['stopBase']*a
    if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
    else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
    rr=rr_target(model,score,p['type']);tp=en+rr*risk if side=='BUY' else en-rr*risk
    return sl,tp,rr,{'lookbackM15':40,'atrFloorMultiple':round(1.2*p['stopBase'],3),'structure':struct,'atrM15':a}

def pages(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return [v6.bybit_future(sym,cut,end)]
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.append([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return out

def evaluate(source,sym,side,en,sl,tp,cut):
    seen=0;mfe=mae=0.
    for cs in pages(source,sym,cut):
        seen+=len(cs)
        for x in cs:
            if side=='BUY':mfe=max(mfe,x['high']-en);mae=max(mae,en-x['low']);hs=x['low']<=sl;ht=x['high']>=tp
            else:mfe=max(mfe,en-x['low']);mae=max(mae,x['high']-en);hs=x['high']>=sl;ht=x['low']<=tp
            if hs and ht:return {'result':'AMBIGUOUS','mfe':mfe,'mae':mae,'candles':seen}
            if hs:return {'result':'SL','mfe':mfe,'mae':mae,'candles':seen}
            if ht:return {'result':'TP','mfe':mfe,'mae':mae,'candles':seen}
    return {'result':'UNRESOLVED','mfe':mfe,'mae':mae,'candles':seen}

def run(label,cutoff,isblind):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);loaded=[];errs=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);loaded.append((sym,source,fr,su))
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':cutoff,'error':str(e)})
    state=state_stats(loaded);rows=[]
    for sym,source,fr,su in loaded:
        side,score,model=direction(sym,fr,su,bf,bm,state);en=fr['M5'][-1]['close'];sl,tp,rr,bar=barriers(sym,side,en,su,fr,model,score);res=evaluate(source,sym,side,en,sl,tp,cut)
        rows.append({'symbol':sym+'USDT','cutoff':cutoff,'source':source,'blind':isblind,'decision':side,'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':round(rr,3),'barrier':bar,'model':model,'outcome':res})
    rows+=errs;usable=[r for r in rows if r.get('decision')];resolved=[r for r in usable if r['outcome']['result'] in ('TP','SL')];wins=[r for r in resolved if r['outcome']['result']=='TP'];losses=[r for r in resolved if r['outcome']['result']=='SL'];total=sum(r['plannedRR'] if r['outcome']['result']=='TP' else -1 for r in resolved)
    s={'label':label,'cutoff':cutoff,'isTrueBlind':isblind,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(r['plannedRR'] for r in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'marketState':state}
    return {'summary':s,'tests':rows}

def main():
    samples={label:run(label,c,b) for label,c,b in CUTOFFS};p={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V14 state-aware forced-market candidate: V6 structural core + modest time-series momentum (H1 4h/12h, M15 1h) + breadth acceleration + range location; 10h M15 structural SL with coin-profile 1.2x ATR floor; RR floor 1.50 and dynamic 1.50-2.05 by regime/confidence; no WAIT/LIMIT.','weights':W,'samples':samples};json.dump(p,open('data/blind_backtest_v14.json','w'),indent=2);print(json.dumps({k:v['summary'] for k,v in samples.items()},indent=2))
if __name__=='__main__':main()
