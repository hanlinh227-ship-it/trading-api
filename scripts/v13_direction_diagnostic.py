#!/usr/bin/env python3
import json, os, sys
from collections import defaultdict
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

CUTOFFS=["2026-08-13T12:00:00Z","2026-08-12T12:00:00Z"]
HOURS=96
SF=1.2; LB=40; RR=1.5

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'): return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out += [x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt];cur=nxt
    return sorted(out,key=lambda x:x['ts'])
def result(side,en,sl,tp,cs):
    for x in cs:
        if side=='BUY': hs=x['low']<=sl;ht=x['high']>=tp
        else: hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return 'AMB'
        if hs:return 'SL'
        if ht:return 'TP'
    return 'UNR'
def barriers(side,en,a,base,fr):
    floor=SF*base*a; recent=fr['M15'][-LB:]
    if side=='BUY':risk=max(floor,en-min(x['low'] for x in recent));return en-risk,en+RR*risk
    risk=max(floor,max(x['high'] for x in recent)-en);return en+risk,en-RR*risk
def bucket(sc):
    a=abs(sc)
    return '0-1' if a<1 else '1-3' if a<3 else '3-5' if a<5 else '5+'
def summarize(rows,key):
    g=defaultdict(lambda:{'n':0,'tp':0,'sl':0,'unr':0,'oppTp':0,'oppSl':0})
    for r in rows:
        z=g[str(r[key])];z['n']+=1;z['tp']+=r['result']=='TP';z['sl']+=r['result']=='SL';z['unr']+=r['result'] not in ('TP','SL');z['oppTp']+=r['opposite']=='TP';z['oppSl']+=r['opposite']=='SL'
    for z in g.values():
        n=z['tp']+z['sl'];z['winRate']=round(100*z['tp']/n,2) if n else None
        no=z['oppTp']+z['oppSl'];z['oppositeWinRate']=round(100*z['oppTp']/no,2) if no else None
    return dict(g)
def main():
    allout={}
    for cutoff in CUTOFFS:
        cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);temp=[]
        # First pass for breadth from all usable coins.
        loaded=[]
        for sym in v6.COINS:
            try:
                source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);loaded.append((sym,source,fr,su))
            except Exception:pass
        breadth4=sum(v6.ret(fr['H1'],4)>0 for _,_,fr,_ in loaded)/len(loaded)
        breadth12=sum(v6.ret(fr['H1'],12)>0 for _,_,fr,_ in loaded)/len(loaded)
        for sym,source,fr,su in loaded:
            side,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm);cs=future(source,sym,cut);base=v6.profile(sym)['stopBase'];a=su['M15']['atr14'] or en*.01
            sl,tp=barriers(side,en,a,base,fr);res=result(side,en,sl,tp,cs)
            oside='SELL' if side=='BUY' else 'BUY';osl,otp=barriers(oside,en,a,base,fr);ores=result(oside,en,osl,otp,cs)
            temp.append({'symbol':sym,'profile':v6.profile(sym)['type'],'regime':model['regime'],'side':side,'score':round(sc,3),'scoreBucket':bucket(sc),'result':res,'opposite':ores,'h1ret4':v6.ret(fr['H1'],4),'h1ret12':v6.ret(fr['H1'],12),'m15ret4':v6.ret(fr['M15'],4),'rangePos':model['rangePositionH1'],'chase':model['chaseAdjustment'],'m15Sweep':model['m15Sweep'],'m5Sweep':model['m5Sweep']})
        allout[cutoff]={'breadth4h':round(breadth4,3),'breadth12h':round(breadth12,3),'byProfile':summarize(temp,'profile'),'byRegime':summarize(temp,'regime'),'bySide':summarize(temp,'side'),'byScoreBucket':summarize(temp,'scoreBucket'),'trades':temp}
    p={'generatedAt':datetime.now(timezone.utc).isoformat(),'policy':{'stopFactor':SF,'lookback':LB,'rr':RR},'samples':allout}
    with open('data/v13_direction_diagnostic.json','w') as f:json.dump(p,f,indent=2)
    print(json.dumps({c:{'breadth4h':x['breadth4h'],'breadth12h':x['breadth12h'],'byRegime':x['byRegime'],'bySide':x['bySide'],'byScoreBucket':x['byScoreBucket']} for c,x in allout.items()},indent=2))
if __name__=='__main__':main()
