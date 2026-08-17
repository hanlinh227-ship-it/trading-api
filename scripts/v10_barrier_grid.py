#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

CUTOFF="2026-08-13T12:00:00Z"
STOP_FACTORS=[0.75,0.9,1.05,1.2,1.4]
LOOKBACKS=[6,12,20,32]
RRS=[1.3,1.5,1.7,2.0,2.3]

def future_candles(source,sym,cut):
    end=cut+v6.MAX_FORWARD_HOURS*3600000
    if source.startswith("Bybit"):
        return v6.bybit_future(sym,cut,end)
    out=[]; cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000)
        out.extend([x for x in v6.okx_future_page(f"{sym}-USDT",cur,nxt) if cur<=x["ts"]<nxt]); cur=nxt
    return sorted(out,key=lambda x:x["ts"])

def result(side,en,sl,tp,cs):
    for x in cs:
        if side=="BUY": hs=x["low"]<=sl; ht=x["high"]>=tp
        else: hs=x["high"]>=sl; ht=x["low"]<=tp
        if hs and ht:return "AMB"
        if hs:return "SL"
        if ht:return "TP"
    return "UNR"

def main():
    cut=v6.iso_ms(CUTOFF); bs,bf,bm=v6.load_frames("BTC",cut); rows=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=="BTC" else v6.load_frames(sym,cut)
            side,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            cs=future_candles(source,sym,cut); a=su["M15"]["atr14"] or en*.01; base=v6.profile(sym)["stopBase"]
            rows.append((sym,side,en,a,base,fr,cs))
        except Exception: pass
    grid=[]
    for sf in STOP_FACTORS:
      for lb in LOOKBACKS:
       for rr in RRS:
        w=l=u=0
        for sym,side,en,a,base,fr,cs in rows:
            recent=fr["M15"][-lb:]
            floor=base*sf*a
            if side=="BUY":
                struct=min(x["low"] for x in recent); risk=max(floor,en-struct); sl=en-risk; tp=en+rr*risk
            else:
                struct=max(x["high"] for x in recent); risk=max(floor,struct-en); sl=en+risk; tp=en-rr*risk
            r=result(side,en,sl,tp,cs)
            if r=="TP":w+=1
            elif r=="SL":l+=1
            else:u+=1
        n=w+l; exp=(w*rr-l)/n if n else None; win=100*w/n if n else None
        grid.append({"stopFactor":sf,"lookback":lb,"rr":rr,"wins":w,"losses":l,"unresolved":u,"winRate":round(win,2) if win is not None else None,"expectancyR":round(exp,3) if exp is not None else None})
    feasible=[x for x in grid if x["rr"]>=1.5]
    bywin=sorted(feasible,key=lambda x:(x["winRate"],x["expectancyR"]),reverse=True)[:15]
    byexp=sorted(feasible,key=lambda x:(x["expectancyR"],x["winRate"]),reverse=True)[:15]
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"cutoff":CUTOFF,"trades":len(rows),"topByWinRRge1_5":bywin,"topByExpectancyRRge1_5":byexp,"grid":grid}
    with open("data/v10_barrier_grid.json","w") as f:json.dump(payload,f,indent=2)
    print(json.dumps({"trades":len(rows),"topWin":bywin[:5],"topExp":byexp[:5]},indent=2))
if __name__=="__main__":main()
