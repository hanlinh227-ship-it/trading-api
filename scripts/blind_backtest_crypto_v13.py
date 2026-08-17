#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
LABEL='FRESH_BLIND_2026-08-05_12UTC'
CUTOFF='2026-08-05T12:00:00Z'
HOURS=96
LOOKBACK=48
STOP_FACTOR=.95

def choose_side(base_side, model):
    rg=model['regime']; pos=model.get('rangePositionH1',.5); htf=model.get('htfScore',0); ltf=model.get('ltfScore',0)
    htf_side='BUY' if htf>=0 else 'SELL'; ltf_side='BUY' if ltf>=0 else 'SELL'
    if rg=='trend': return htf_side
    if rg=='range': return 'SELL' if pos>=.55 else 'BUY'
    return htf_side if abs(htf)>=2.5 else ltf_side

def planned_rr(model, score):
    return 1.70 if model['regime']=='trend' else 1.50

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
    cut=v6.iso_ms(CUTOFF);bs,bf,bm=v6.load_frames('BTC',cut);rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            bside,score,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            side=choose_side(bside,model);a=su['M15']['atr14'] or en*.01;base=v6.profile(sym)['stopBase'];recent=fr['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a
            if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk
            else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk
            rr=planned_rr(model,score);tp=en+rr*risk if side=='BUY' else en-rr*risk
            res=evaluate(side,en,sl,tp,future(source,sym,cut))
            rows.append({'symbol':sym+'USDT','cutoff':CUTOFF,'source':source,'blind':True,'decision':side,'baseDecision':bside,'score':round(score,3),'entry':en,'sl':sl,'tp':tp,'plannedRR':rr,'barrier':{'lookbackM15':LOOKBACK,'stopFactor':STOP_FACTOR,'structure':struct,'atrM15':a},'model':model,'outcome':res})
        except Exception as e:rows.append({'symbol':sym+'USDT','cutoff':CUTOFF,'error':str(e)})
    usable=[r for r in rows if r.get('decision')];resolved=[r for r in usable if r.get('outcome',{}).get('result') in ('TP','SL')];wins=[r for r in resolved if r['outcome']['result']=='TP'];loss=[r for r in resolved if r['outcome']['result']=='SL']
    total=sum(r['plannedRR'] if r['outcome']['result']=='TP' else -1 for r in resolved)
    summary={'label':LABEL,'cutoff':CUTOFF,'isTrueBlind':True,'requested':len(v6.COINS),'marketTrades':len(usable),'dataErrors':len(rows)-len(usable),'resolved':len(resolved),'wins':len(wins),'losses':len(loss),'unresolved':len(usable)-len(resolved),'winRateResolved':round(100*len(wins)/len(resolved),2) if resolved else None,'avgPlannedRR':round(sum(r['plannedRR'] for r in resolved)/len(resolved),3) if resolved else None,'expectancyR':round(total/len(resolved),3) if resolved else None}
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V13 locked HTF-first forced-market: trend follows HTF; range fades H1 location; transition HTF-first with LTF fallback; 48xM15 structural invalidation plus profile ATR floor; RR 1.7 trend / 1.5 otherwise; no WAIT/LIMIT; future hidden until decision.','summary':summary,'tests':rows}
    with open('data/blind_backtest_v13.json','w') as f:json.dump(payload,f,indent=2)
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
# trigger-v2