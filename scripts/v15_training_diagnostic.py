#!/usr/bin/env python3
import json, os, sys, statistics
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

CUTOFFS=['2026-08-07T12:00:00Z','2026-08-08T12:00:00Z','2026-08-09T12:00:00Z']
SF=1.2;LB=40;RR=1.5;HOURS=96

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith('Bybit'):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out += [x for x in v6.okx_future_page(f'{sym}-USDT',cur,nxt) if cur<=x['ts']<nxt];cur=nxt
    return sorted(out,key=lambda x:x['ts'])
def result(side,en,sl,tp,cs):
    for i,x in enumerate(cs):
        if side=='BUY':hs=x['low']<=sl;ht=x['high']>=tp
        else:hs=x['high']>=sl;ht=x['low']<=tp
        if hs and ht:return {'result':'AMB','bars':i+1}
        if hs:return {'result':'SL','bars':i+1}
        if ht:return {'result':'TP','bars':i+1}
    return {'result':'UNR','bars':len(cs)}
def barriers(side,en,a,base,fr):
    floor=SF*base*a;recent=fr['M15'][-LB:]
    if side=='BUY':risk=max(floor,en-min(x['low'] for x in recent));return en-risk,en+RR*risk
    risk=max(floor,max(x['high'] for x in recent)-en);return en+risk,en-RR*risk
def run(cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames('BTC',cut);loaded=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=='BTC' else v6.load_frames(sym,cut);loaded.append((sym,source,fr,su))
        except Exception:pass
    rets4=[v6.ret(fr['H1'],4) for _,_,fr,_ in loaded];rets12=[v6.ret(fr['H1'],12) for _,_,fr,_ in loaded]
    state={'breadth4h':sum(x>0 for x in rets4)/len(rets4),'breadth12h':sum(x>0 for x in rets12)/len(rets12),'dispersion4h':statistics.pstdev(rets4),'median4h':statistics.median(rets4),'median12h':statistics.median(rets12)}
    trades=[]
    for sym,source,fr,su in loaded:
        side,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm);cs=future(source,sym,cut);base=v6.profile(sym)['stopBase'];a=su['M15']['atr14'] or en*.01
        sl,tp=barriers(side,en,a,base,fr);r=result(side,en,sl,tp,cs);oside='SELL' if side=='BUY' else 'BUY';osl,otp=barriers(oside,en,a,base,fr);o=result(oside,en,osl,otp,cs)
        trades.append({'symbol':sym,'profile':v6.profile(sym)['type'],'regime':model['regime'],'v6Side':side,'v6Score':sc,'current':r,'opposite':o,'h1ret4':v6.ret(fr['H1'],4),'h1ret12':v6.ret(fr['H1'],12),'m15ret4':v6.ret(fr['M15'],4),'m15ret12':v6.ret(fr['M15'],12),'rangePos':model['rangePositionH1'],'chase':model['chaseAdjustment'],'m15Sweep':model['m15Sweep'],'m5Sweep':model['m5Sweep'],'state':state})
    return {'state':state,'trades':trades}
def main():
    p={'generatedAt':datetime.now(timezone.utc).isoformat(),'policy':{'stopFactor':SF,'lookback':LB,'rr':RR,'hours':HOURS},'samples':{c:run(c) for c in CUTOFFS}}
    json.dump(p,open('data/v15_training_diagnostic.json','w'),indent=2)
    print(json.dumps({c:{'state':s['state'],'trades':len(s['trades'])} for c,s in p['samples'].items()},indent=2))
if __name__=='__main__':main()
