#!/usr/bin/env python3
import json, os, sys, itertools
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

DEV=[('AUG12','2026-08-12T12:00:00Z'),('AUG05','2026-08-05T12:00:00Z'),('AUG03','2026-08-03T12:00:00Z')]
POLICIES=['short','mid','weekly','blend']
RR_MODES=['static15','confidence17']
LB=48;SF=.75;HOURS=96

def norm(r,s):return max(-2,min(2,r/s))
def features(sym,fr,su,bf):
    r6=v6.ret(fr['H1'],6);r24=v6.ret(fr['H1'],24);r72=v6.ret(fr['H4'],18);r7=v6.ret(fr['H4'],42);r14=v6.ret(fr['H4'],84)
    b24=v6.ret(bf['H1'],24);b7=v6.ret(bf['H4'],42);rs24=r24-b24;rs7=r7-b7
    st4=v6.structure(fr['H4']);st1=v6.structure(fr['H1']);cl=su['H4']['close'];e50=su['H4']['ema50'];e200=su['H4']['ema200'];eb=(1 if e50 and cl>e50 else -1 if e50 else 0)+(0.5 if e200 and cl>e200 else -0.5 if e200 else 0)
    return {'r6':r6,'r24':r24,'r72':r72,'r7d':r7,'r14d':r14,'rs24':rs24,'rs7d':rs7,'st4':st4,'st1':st1,'emaBias':eb}
def score(policy,f,sym):
    common=.8*f['st4']+.45*f['st1']+.4*f['emaBias'];rs=0 if sym=='BTC' else .35*norm(f['rs24'],.025)+.35*norm(f['rs7d'],.07)
    if policy=='short':return .8*norm(f['r6'],.01)+1.1*norm(f['r24'],.025)+1.3*norm(f['r72'],.05)+common+rs
    if policy=='mid':return .7*norm(f['r24'],.025)+1.2*norm(f['r72'],.05)+1.5*norm(f['r7d'],.08)+common+rs
    if policy=='weekly':return .7*norm(f['r72'],.05)+1.4*norm(f['r7d'],.08)+1.4*norm(f['r14d'],.12)+common+rs
    return .45*norm(f['r6'],.01)+.75*norm(f['r24'],.025)+1.0*norm(f['r72'],.05)+1.15*norm(f['r7d'],.08)+.9*norm(f['r14d'],.12)+common+rs

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
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);rows.append({'sym':sym,'source':source,'fr':fr,'su':su,'en':fr['M5'][-1]['close'],'f':features(sym,fr,su,bf),'future':future(source,sym,cut)})
        except Exception:pass
    return rows
def evaluate(rows,p,mode):
    w=l=u=0;total=0;rrs=[]
    for r in rows:
        sc=score(p,r['f'],r['sym']);side='BUY' if sc>=0 else 'SELL';rr=1.7 if mode=='confidence17' and abs(sc)>=2.5 else 1.5;en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-LB:];floor=SF*base*a
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        z=outcome(side,en,sl,tp,r['future'])
        if z=='TP':w+=1;total+=rr;rrs.append(rr)
        elif z=='SL':l+=1;total-=1;rrs.append(rr)
        else:u+=1
    n=w+l;return {'wins':w,'losses':l,'unresolved':u,'winRate':round(100*w/n,2) if n else None,'avgRR':round(sum(rrs)/n,3) if n else None,'expectancyR':round(total/n,3) if n else None}
def main():
    ds={k:load(c) for k,c in DEV};grid=[]
    for p,m in itertools.product(POLICIES,RR_MODES):
        per={k:evaluate(v,p,m) for k,v in ds.items()};minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgwr=sum(x['winRate'] for x in per.values())/len(per);avgexp=sum(x['expectancyR'] for x in per.values())/len(per);avgrr=sum(x['avgRR'] for x in per.values())/len(per);rob=minwr+12*minexp+4*(avgrr-1.5)+.1*avgwr+3*avgexp
        grid.append({'policy':p,'rrMode':m,'perSample':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgWinRate':round(avgwr,2),'avgRR':round(avgrr,3),'avgExpectancyR':round(avgexp,3),'robustScore':round(rob,3)})
    top=sorted(grid,key=lambda x:x['robustScore'],reverse=True)
    with open('data/v16_horizon_dev.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V16 development: compare short 6h-72h momentum with 1w/2w horizons suggested by crypto momentum literature; structure+EMA+BTC relative strength; structural 48xM15 stop; RR1.5 or confidence1.7.','top':top,'grid':grid},f,indent=2)
    print(json.dumps({'top':top},indent=2))
if __name__=='__main__':main()
