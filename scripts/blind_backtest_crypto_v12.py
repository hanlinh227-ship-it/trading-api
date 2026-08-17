#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

# V12 policy is locked. The fresh sample below was not used for tuning.
CUTOFFS=[
    ("OLD_REGRESSION_2026-08-13_12UTC","2026-08-13T12:00:00Z",False),
    ("FRESH_BLIND_2026-08-12_12UTC","2026-08-12T12:00:00Z",True),
]
MAX_FORWARD_HOURS=96


def dynamic_rr(model, score):
    rg=model["regime"]; c=abs(score)
    if rg=="trend": rr=1.80 if c<4 else 1.95 if c<7 else 2.10
    elif rg=="transition": rr=1.60 if c<4 else 1.75 if c<7 else 1.90
    else: rr=1.45 if c<4 else 1.60 if c<7 else 1.75
    return rr

def barriers(sym,side,en,sums,frames,model,score):
    a=sums["M15"]["atr14"] or en*.01; base=v6.profile(sym)["stopBase"]
    # Regression grid showed 32 M15 bars (~8h) captures crypto stop-hunts/sweeps much better than 3h stops.
    recent=frames["M15"][-32:]
    floor=.75*base*a
    if side=="BUY":
        structural=min(x["low"] for x in recent); risk=max(floor,en-structural); sl=en-risk
    else:
        structural=max(x["high"] for x in recent); risk=max(floor,structural-en); sl=en+risk
    rr=dynamic_rr(model,score)
    tp=en+rr*risk if side=="BUY" else en-rr*risk
    return sl,tp,rr,{"lookbackM15":32,"atrFloorMultiple":round(.75*base,3),"structuralInvalidation":structural,"atrM15":a}

def future_pages(source,sym,cut):
    end=cut+MAX_FORWARD_HOURS*3600000
    if source.startswith("Bybit"): return [v6.bybit_future(sym,cut,end)]
    pages=[]; cur=cut
    while cur<end:
        nxt=min(end,cur+24*3600000); pages.append([x for x in v6.okx_future_page(f"{sym}-USDT",cur,nxt) if cur<=x["ts"]<nxt]); cur=nxt
    return pages

def evaluate(source,sym,side,en,sl,tp,cut):
    mfe=mae=0.; seen=0
    for cs in future_pages(source,sym,cut):
        seen+=len(cs)
        for x in cs:
            if side=="BUY": mfe=max(mfe,x["high"]-en); mae=max(mae,en-x["low"]); hs=x["low"]<=sl; ht=x["high"]>=tp
            else: mfe=max(mfe,en-x["low"]); mae=max(mae,x["high"]-en); hs=x["high"]>=sl; ht=x["low"]<=tp
            if hs and ht:return {"result":"AMBIGUOUS","mfe":mfe,"mae":mae,"candles":seen}
            if hs:return {"result":"SL","mfe":mfe,"mae":mae,"candles":seen}
            if ht:return {"result":"TP","mfe":mfe,"mae":mae,"candles":seen}
    return {"result":"UNRESOLVED","mfe":mfe,"mae":mae,"candles":seen}

def run(label,cutoff,isblind):
    cut=v6.iso_ms(cutoff); bs,bf,bm=v6.load_frames("BTC",cut); out=[]
    for sym in v6.COINS:
        try:
            source,fr,su=(bs,bf,bm) if sym=="BTC" else v6.load_frames(sym,cut)
            side,sc,en,_,_,_,model=v6.choose(sym,su,fr,bf,bm)
            sl,tp,rr,bar=barriers(sym,side,en,su,fr,model,sc); res=evaluate(source,sym,side,en,sl,tp,cut)
            out.append({"symbol":sym+"USDT","cutoff":cutoff,"source":source,"blind":isblind,"decision":side,"score":round(sc,3),"entry":en,"sl":sl,"tp":tp,"plannedRR":round(rr,3),"barrier":bar,"model":model,"outcome":res})
        except Exception as e:out.append({"symbol":sym+"USDT","cutoff":cutoff,"error":str(e)})
    usable=[r for r in out if r.get("decision")]; resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]
    w=[r for r in resolved if r["outcome"]["result"]=="TP"]; l=[r for r in resolved if r["outcome"]["result"]=="SL"]
    total=sum(r["plannedRR"] if r["outcome"]["result"]=="TP" else -1 for r in resolved)
    s={"label":label,"cutoff":cutoff,"isTrueBlind":isblind,"requested":len(v6.COINS),"marketTrades":len(usable),"dataErrors":len(out)-len(usable),"resolved":len(resolved),"wins":len(w),"losses":len(l),"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*len(w)/len(resolved),2) if resolved else None,"avgPlannedRR":round(sum(r["plannedRR"] for r in resolved)/len(resolved),3) if resolved else None,"expectancyR":round(total/len(resolved),3) if resolved else None}
    return {"summary":s,"tests":out}

def main():
    samples={label:run(label,c,b) for label,c,b in CUTOFFS}
    p={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V12 forced-market locked candidate: V6 direction engine; 8h (32xM15) structural invalidation SL with coin-profile ATR floor; dynamic RR by regime/confidence: range 1.45-1.75, transition 1.60-1.90, trend 1.80-2.10; no universal TP/SL prices; no WAIT/LIMIT; future hidden until decision.","samples":samples}
    with open("data/blind_backtest_v12.json","w") as f:json.dump(p,f,indent=2)
    print(json.dumps({k:v["summary"] for k,v in samples.items()},indent=2))
if __name__=="__main__":main()
