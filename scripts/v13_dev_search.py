#!/usr/bin/env python3
import json, os, sys, itertools
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

DEV_CUTOFFS=[('DEV_A','2026-08-13T12:00:00Z'),('DEV_B','2026-08-12T12:00:00Z')]
POLICIES=['base','regime_position','htf_primary','hybrid']
LOOKBACKS=[20,32,48]
STOP_FACTORS=[0.55,0.75,0.95]
RRS=[1.5,1.7,1.9,2.1]
HOURS=96

def side_for(policy, base_side, score, model, sums):
    rg=model['regime']; pos=model.get('rangePositionH1',.5); htf=model.get('htfScore',0); ltf=model.get('ltfScore',0)
    htf_side='BUY' if htf>=0 else 'SELL'; ltf_side='BUY' if ltf>=0 else 'SELL'
    if policy=='base': return base_side
    if policy=='htf_primary':
        if rg=='trend': return htf_side
        if rg=='range': return 'SELL' if pos>=.55 else 'BUY'
        return htf_side if abs(htf)>=2.5 else ltf_side
    if policy=='regime_position':
        if rg=='trend': return htf_side
        if pos>=.65:return 'SELL'
        if pos<=.35:return 'BUY'
        return htf_side
    if rg=='trend': return htf_side
    if rg=='range': return 'SELL' if pos>=.55 else 'BUY'
    chase=model.get('chaseAdjustment',0)
    if pos>=.72:return 'SELL'
    if pos<=.28:return 'BUY'
    if abs(chase)>=1.6 and abs(htf)<7:return 'SELL' if pos>=.5 else 'BUY'
    return htf_side if abs(htf)>=3 else ltf_side

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

def load_cut(cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut)
            bside,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            rows.append({'sym':sym,'source':source,'fr':fr,'su':su,'baseSide':bside,'score':sc,'en':en,'model':model,'future':future(source,sym,cut)})
        except Exception:pass
    return rows

def eval_cfg(rows,policy,lb,sf,rr):
    w=l=u=0
    for r in rows:
        side=side_for(policy,r['baseSide'],r['score'],r['model'],r['su']);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-lb:];floor=sf*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        z=outcome(side,en,sl,tp,r['future'])
        if z=='TP':w+=1
        elif z=='SL':l+=1
        else:u+=1
    n=w+l;wr=100*w/n if n else 0;exp=(w*rr-l)/n if n else -99
    return {'wins':w,'losses':l,'unresolved':u,'winRate':round(wr,2),'expectancyR':round(exp,3)}

def main():
    data={name:load_cut(cut) for name,cut in DEV_CUTOFFS};grid=[]
    for policy,lb,sf,rr in itertools.product(POLICIES,LOOKBACKS,STOP_FACTORS,RRS):
        per={k:eval_cfg(v,policy,lb,sf,rr) for k,v in data.items()}
        minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgwr=sum(x['winRate'] for x in per.values())/len(per);avgexp=sum(x['expectancyR'] for x in per.values())/len(per)
        robust=minwr + 8*minexp + 2*(rr-1.5) + .15*avgwr + 3*avgexp
        grid.append({'policy':policy,'lookback':lb,'stopFactor':sf,'rr':rr,'perSample':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgWinRate':round(avgwr,2),'avgExpectancyR':round(avgexp,3),'robustScore':round(robust,3)})
    feasible=[x for x in grid if x['minExpectancyR']>0 and x['minWinRate']>=40 and x['rr']>=1.5]
    top=sorted(feasible,key=lambda x:(x['robustScore'],x['minWinRate'],x['rr']),reverse=True)[:20]
    payload={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V13 development-only robust search; no fresh cutoff used','devCutoffs':DEV_CUTOFFS,'top':top,'grid':grid}
    with open('data/v13_dev_search.json','w') as f:json.dump(payload,f,indent=2)
    print(json.dumps({'top':top[:10]},indent=2))
if __name__=='__main__':main()
# trigger-v2