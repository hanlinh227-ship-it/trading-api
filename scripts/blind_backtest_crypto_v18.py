#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import blind_backtest_crypto_v17 as v17

# Fresh unseen cutoff. V18 changes RR only; direction keeps the V17 price/structure model.
LABEL='FRESH_BLIND_2026-07-30_12UTC'; CUTOFF='2026-07-30T12:00:00Z'
LOOKBACK=48; STOP_FACTOR=.75

def rr_for(score,model):
    c=abs(score)
    if c>=5.0 and model['regime']=='trend': return 1.90
    if c>=2.5: return 1.70
    return 1.50

def main():
    cut=v6.iso_ms(CUTOFF);bs,bf,bm=v6.load_frames('BTC',cut);tmp=[];errs=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            _,_,_,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'en':fr['M5'][-1]['close'],'model':model,'f':v17.features(sym,fr,su,bf)})
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':CUTOFF,'error':str(e)})
    breadth=sum(r['f']['r24']>0 for r in tmp)/len(tmp) if tmp else .5;rows=[]
    for r in tmp:
        sym=r['sym'];fake={'available':False,'oiChange4h':None,'funding':None,'fundingZ':0.0,'signal':0.0}
        sc=v17.score_trade(sym,r['f'],r['su'],fake,breadth);side='BUY' if sc>=0 else 'SELL';en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
        rr=rr_for(sc,r['model']);tp=en+rr*risk if side=='BUY' else en-rr*risk;res=v17.evaluate(side,en,sl,tp,v17.future(r['source'],sym,cut))
        rows.append({'symbol':sym+'USDT','cutoff':CUTOFF,'source':r['source'],'blind':True,'decision':side,'score':round(sc,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(breadth,3),'features':r['f'],'model':r['model'],'outcome':res})
    rows+=errs;usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    s={'label':LABEL,'cutoff':CUTOFF,'isTrueBlind':True,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3)}
    with open('data/blind_backtest_v18.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V18 true blind: V17 multi-horizon price/structure direction (no unavailable derivatives dependency); 48xM15 structure SL + .75 profile ATR floor; RR 1.5 base, 1.7 when abs score>=2.5, 1.9 only high-confidence trend; no WAIT/LIMIT.','summary':s,'tests':rows},f,indent=2)
    print(json.dumps(s,indent=2))
if __name__=='__main__':main()
