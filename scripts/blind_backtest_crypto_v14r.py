#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import v14_dev_search as v14
LABEL='FRESH_BLIND_2026-08-03_12UTC';CUTOFF='2026-08-03T12:00:00Z';HOURS=96;LOOKBACK=48;STOP_FACTOR=.75
# Locked from development on Aug12 + Aug05 before reading Aug03 outcome.
BASE_RR=1.5;HIGH_RR=1.7;CONF_THRESHOLD=2.5

def rr_for(feat): return HIGH_RR if abs(feat['momScore'])>=CONF_THRESHOLD else BASE_RR

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out.extend([x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt]);cur=nxt
    return sorted(out,key=lambda x:x['ts'])

def evaluate(side,en,sl,tp,cs):
    mfe=mae=0.0
    for i,x in enumerate(cs,1):
        if side=='BUY':mfe=max(mfe,x['high']-en);mae=max(mae,en-x['low']);hs=x['low']<=sl;ht=x['high']>=tp
        else:mfe=max(mfe,en-x['low']);mae=max(mae,x['high']-en);hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return {'result':'AMBIGUOUS','mfe':mfe,'mae':mae,'candles':i}
        if hs:return {'result':'SL','mfe':mfe,'mae':mae,'candles':i}
        if ht:return {'result':'TP','mfe':mfe,'mae':mae,'candles':i}
    return {'result':'UNRESOLVED','mfe':mfe,'mae':mae,'candles':len(cs)}

def main():
    cut=v6.iso_ms(CUTOFF);bs,bf,bm=v6.load_frames('BTC',cut);errs=[];tmp=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);base,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm);feat=v14.momentum_features(sym,fr,su,bf);tmp.append({'sym':sym,'source':source,'fr':fr,'su':su,'baseSide':base,'score':sc,'en':en,'model':model,'feat':feat})
        except Exception as e:errs.append({'symbol':sym+'USDT','cutoff':CUTOFF,'error':str(e)})
    breadth=sum(r['feat']['r24']>0 for r in tmp)/len(tmp) if tmp else .5;rows=[]
    for r in tmp:
        sym=r['sym'];source=r['source'];fr=r['fr'];su=r['su'];en=r['en'];side=v14.choose_side('tsmom_structure',r,breadth);a=su['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=fr['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a;rr=rr_for(r['feat'])
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        rows.append({'symbol':sym+'USDT','cutoff':CUTOFF,'source':source,'blind':True,'decision':side,'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'breadth':round(breadth,3),'momentum':r['feat'],'model':r['model'],'outcome':evaluate(side,en,sl,tp,future(source,sym,cut))})
    rows+=errs;usable=[x for x in rows if x.get('decision')];resolved=[x for x in usable if x.get('outcome',{}).get('result') in ('TP','SL')];w=[x for x in resolved if x['outcome']['result']=='TP'];l=[x for x in resolved if x['outcome']['result']=='SL'];total=sum(x['plannedRR'] if x['outcome']['result']=='TP' else -1 for x in resolved)
    summary={'label':LABEL,'cutoff':CUTOFF,'isTrueBlind':True,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(errs),'resolved':len(resolved),'wins':len(w),'losses':len(l),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(w)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(x['plannedRR'] for x in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None,'breadth':round(breadth,3)}
    with open('data/blind_backtest_v14r.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V14R locked forced-market: V14 time-series momentum+structure direction; 48xM15 structural SL with .75 profile ATR floor; RR1.5 base and 1.7 when abs momentum score>=2.5; rules locked on Aug12/Aug05 before Aug03 outcome was read.','summary':summary,'tests':rows},f,indent=2)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
