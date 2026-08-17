#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

CUTOFFS=["2026-08-13T12:00:00Z","2026-08-12T12:00:00Z"]
STOP_FACTORS=[0.65,0.75,0.9,1.05,1.2]
LOOKBACKS=[12,20,24,32,40]
RRS=[1.4,1.5,1.6,1.7,1.8,2.0]
HOURS=96

def future(source,sym,cut):
    end=cut+HOURS*3600000
    if source.startswith("Bybit"):return v6.bybit_future(sym,cut,end)
    out=[];cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000);out += [x for x in v6.okx_future_page(f"{sym}-USDT",cur,nxt) if cur<=x["ts"]<nxt];cur=nxt
    return sorted(out,key=lambda x:x["ts"])
def outcome(side,en,sl,tp,cs):
    for x in cs:
        if side=="BUY":hs=x["low"]<=sl;ht=x["high"]>=tp
        else:hs=x["high"]>=sl;ht=x["low"]<=tp
        if hs and ht:return "AMB"
        if hs:return "SL"
        if ht:return "TP"
    return "UNR"
def dataset(cutoff):
    cut=v6.iso_ms(cutoff);bs,bf,bm=v6.load_frames("BTC",cut);rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=="BTC" else v6.load_frames(sym,cut)
            side,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            rows.append({"sym":sym,"source":source,"frames":fr,"sums":su,"side":side,"score":sc,"entry":en,"profile":v6.profile(sym),"model":model,"future":future(source,sym,cut)})
        except Exception:pass
    return rows
def test(rows,sf,lb,rr):
    w=l=u=0
    for r in rows:
        a=r["sums"]["M15"]["atr14"] or r["entry"]*.01; floor=sf*r["profile"]["stopBase"]*a;recent=r["frames"]["M15"][-lb:];en=r["entry"];side=r["side"]
        if side=="BUY":risk=max(floor,en-min(x["low"] for x in recent));sl=en-risk;tp=en+rr*risk
        else:risk=max(floor,max(x["high"] for x in recent)-en);sl=en+risk;tp=en-rr*risk
        z=outcome(side,en,sl,tp,r["future"])
        if z=="TP":w+=1
        elif z=="SL":l+=1
        else:u+=1
    n=w+l;return {"wins":w,"losses":l,"unresolved":u,"win":100*w/n if n else 0,"exp":(w*rr-l)/n if n else -9}
def main():
    sets={c:dataset(c) for c in CUTOFFS};grid=[]
    for sf in STOP_FACTORS:
      for lb in LOOKBACKS:
       for rr in RRS:
        per={c:test(rows,sf,lb,rr) for c,rows in sets.items()};wins=[x["win"] for x in per.values()];exps=[x["exp"] for x in per.values()]
        grid.append({"stopFactor":sf,"lookback":lb,"rr":rr,"minWin":round(min(wins),2),"avgWin":round(sum(wins)/len(wins),2),"minExp":round(min(exps),3),"avgExp":round(sum(exps)/len(exps),3),"samples":{c:{k:(round(v,3) if isinstance(v,float) else v) for k,v in x.items()} for c,x in per.items()}})
    feasible=[x for x in grid if x["rr"]>=1.5]
    top=sorted(feasible,key=lambda x:(x["minWin"],x["minExp"],x["avgExp"]),reverse=True)[:25]
    topExp=sorted(feasible,key=lambda x:(x["minExp"],x["minWin"],x["avgExp"]),reverse=True)[:25]
    p={"generatedAt":datetime.now(timezone.utc).isoformat(),"cutoffs":CUTOFFS,"topRobustWin":top,"topRobustExpectancy":topExp,"grid":grid}
    with open("data/v13_robust_grid.json","w") as f:json.dump(p,f,indent=2)
    print(json.dumps({"topWin":top[:5],"topExp":topExp[:5]},indent=2))
if __name__=="__main__":main()
