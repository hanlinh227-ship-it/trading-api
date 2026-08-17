#!/usr/bin/env python3
import json, math, os, sys, urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6

# Regression only while tuning. A fresh cutoff is added only after the model is locked.
CUTOFFS = [("OLD_REGRESSION_2026-08-13_12UTC", "2026-08-13T12:00:00Z", False)]


def clamp(x, lo, hi): return max(lo, min(hi, x))
def sign(x): return 1 if x > 0 else -1 if x < 0 else 0

def bybit_list(path, params):
    q = urllib.parse.urlencode(params)
    try:
        d = v6.http(f"{v6.BYBIT_BASE}{path}?{q}")
        if d.get("retCode") != 0: return []
        return ((d.get("result") or {}).get("list")) or []
    except Exception:
        return []

def derivatives_snapshot(sym, cut):
    symbol = sym + "USDT"
    oi = bybit_list("/v5/market/open-interest", {"category":"linear","symbol":symbol,"intervalTime":"1h","endTime":cut,"limit":16})
    oi = sorted([(int(x.get("timestamp",0)), float(x.get("openInterest",0) or 0)) for x in oi if x.get("openInterest")], key=lambda z:z[0])
    funding = bybit_list("/v5/market/funding/history", {"category":"linear","symbol":symbol,"endTime":cut,"limit":24})
    funding = sorted([(int(x.get("fundingRateTimestamp",0)), float(x.get("fundingRate",0) or 0)) for x in funding], key=lambda z:z[0])
    ls = bybit_list("/v5/market/account-ratio", {"category":"linear","symbol":symbol,"period":"1h","endTime":str(cut),"limit":16})
    ls = sorted([(int(x.get("timestamp",0)), float(x.get("buyRatio",0) or 0), float(x.get("sellRatio",0) or 0)) for x in ls], key=lambda z:z[0])
    def pct(a,b): return (a/b-1) if b else 0.0
    oi4 = pct(oi[-1][1], oi[-5][1]) if len(oi)>=5 else 0.0
    oi12 = pct(oi[-1][1], oi[-13][1]) if len(oi)>=13 else oi4
    fr = funding[-1][1] if funding else 0.0
    fr_hist = [x[1] for x in funding[-12:]]
    fr_mean = sum(fr_hist)/len(fr_hist) if fr_hist else 0.0
    fr_dev = fr-fr_mean
    lsr = (ls[-1][1]/ls[-1][2]) if ls and ls[-1][2] else 1.0
    lsr4 = ((ls[-1][1]/ls[-1][2])-(ls[-5][1]/ls[-5][2])) if len(ls)>=5 and ls[-1][2] and ls[-5][2] else 0.0
    return {"available": bool(oi or funding or ls), "oi4h":oi4, "oi12h":oi12, "funding":fr, "fundingDev":fr_dev, "longShort":lsr, "longShort4hChange":lsr4}

def derivative_score(sym, frames, snap):
    if not snap.get("available"): return 0.0
    p4 = v6.ret(frames["H1"], 4)
    p12 = v6.ret(frames["H1"], 12)
    oi4, oi12 = snap["oi4h"], snap["oi12h"]
    sc = 0.0
    # Price + OI together = fresh positioning. Price move with falling OI is less durable.
    sc += sign(p4) * clamp(max(oi4,0)/0.04,0,1.0) * 1.10
    sc += sign(p12) * clamp(max(oi12,0)/0.08,0,1.0) * 0.65
    if oi4 < -0.025: sc -= sign(p4) * 0.55
    if oi12 < -0.05: sc -= sign(p12) * 0.35
    # Crowding/funding is contrarian only at extremes, never a standalone reversal.
    fr = snap["funding"]
    if fr > 0.00035: sc -= clamp(fr/0.001,0,1)*0.55
    elif fr < -0.00035: sc += clamp(abs(fr)/0.001,0,1)*0.55
    lsr = snap["longShort"]
    if lsr > 1.35: sc -= 0.30
    elif lsr < 0.74: sc += 0.30
    return clamp(sc,-2.5,2.5)

def coherence_score(sums, frames):
    weights = {"D1":0.8,"H4":1.25,"H1":1.0,"M15":0.75,"M5":0.45}
    sc=0.0
    for k,w in weights.items():
        tr=sums[k]["trend"]
        sc += w if tr=="bullish" else -w if tr=="bearish" else 0
        sc += 0.20*w*v6.structure(frames[k])
    return sc

def final_score(sym,sums,frames,btc_frames,btc_sums,deriv):
    base, model = v6.directional_score(sym,sums,frames,btc_frames,btc_sums)
    ds = derivative_score(sym,frames,deriv)
    coh = coherence_score(sums,frames)
    rg=model["regime"]
    # Strong HTF coherence is more reliable than tiny forced V6 scores.
    sc = base + 0.45*coh + (0.80 if sym in v6.MEMES or sym in v6.AI or sym in v6.NEW_HIGH_BETA else 0.60)*ds
    # In range, location + sweep should dominate directional trend chasing.
    pos=model["rangePositionH1"]; sw15=model["m15Sweep"]; sw5=model["m5Sweep"]
    if rg=="range":
        sc += (1.1 if pos<=0.22 else -1.1 if pos>=0.78 else 0)
        sc += 0.9*sw15 + 0.45*sw5
    # Avoid continuation immediately after an exhaustion displacement; forced market flips only when evidence is substantial.
    m15=sums["M15"]
    if m15["volumeRatio"]>=3.0 and abs(m15["dist20ATR"])>=1.6:
        sc += -0.9 if m15["dist20ATR"]>0 else 0.9
    if abs(sc)<0.35:
        sc = 0.35 if coh>=0 else -0.35
    model = dict(model); model.update({"derivativeScore":ds,"coherenceScore":coh,"derivatives":deriv})
    return sc,model

def pivot_levels(c, left=2, right=2, lookback=80):
    x=c[-lookback:]; highs=[]; lows=[]
    for i in range(left,len(x)-right):
        if x[i]["high"]>=max(z["high"] for z in x[i-left:i+right+1]): highs.append(x[i]["high"])
        if x[i]["low"]<=min(z["low"] for z in x[i-left:i+right+1]): lows.append(x[i]["low"])
    return highs,lows

def choose_barriers(sym,side,entry,sums,frames,model,score):
    a=sums["M15"]["atr14"] or entry*0.01
    p=v6.profile(sym); typ=p["type"]; rg=model["regime"]
    h15,l15=pivot_levels(frames["M15"],2,2,72); h1,l1=pivot_levels(frames["H1"],2,2,48)
    # Stop uses nearest structural invalidation, but with volatility floor. High beta receives more breathing room.
    floor = {"major":1.05,"l1_l2":1.15,"defi":1.15,"alt":1.20,"ai_high_beta":1.30,"new_high_beta":1.35,"meme":1.40}.get(typ,1.2)*a
    cap = {"major":1.75,"l1_l2":1.95,"defi":1.95,"alt":2.05,"ai_high_beta":2.20,"new_high_beta":2.25,"meme":2.35}.get(typ,2.05)*a
    if side=="BUY":
        below=sorted([z for z in l15[-10:]+l1[-6:] if z<entry], reverse=True)
        struct=below[0] if below else entry-floor
        risk=max(floor, entry-struct+0.10*a); risk=min(risk,cap); sl=entry-risk
    else:
        above=sorted([z for z in h15[-10:]+h1[-6:] if z>entry])
        struct=above[0] if above else entry+floor
        risk=max(floor, struct-entry+0.10*a); risk=min(risk,cap); sl=entry+risk
    # Raise RR with confidence/regime; no universal target. Use the first liquidity pool that clears the minimum RR.
    conf=abs(score)
    if rg=="trend": minrr=1.65 if conf<4 else 1.85 if conf<7 else 2.10
    elif rg=="transition": minrr=1.45 if conf<4 else 1.65 if conf<7 else 1.85
    else: minrr=1.30 if conf<4 else 1.50 if conf<7 else 1.70
    if typ in ("meme","new_high_beta") and rg!="trend": minrr=max(1.25,minrr-0.10)
    target_min=entry+minrr*risk if side=="BUY" else entry-minrr*risk
    if side=="BUY":
        targets=sorted(set([z for z in h15+h1 if z>=target_min]))
        tp=targets[0] if targets else target_min
    else:
        targets=sorted(set([z for z in l15+l1 if z<=target_min]), reverse=True)
        tp=targets[0] if targets else target_min
    rr=abs(tp-entry)/risk if risk else 0
    # Prevent ancient/extreme pivot from creating fantasy RR.
    maxrr=2.6 if rg=="trend" and conf>=5 else 2.2 if rg=="trend" else 2.0
    if rr>maxrr:
        rr=maxrr; tp=entry+rr*risk if side=="BUY" else entry-rr*risk
    return sl,tp,rr,{"atrM15":a,"minRR":minrr,"structureStopRisk":risk,"targetType":"nearest_liquidity_beyond_minRR"}

def run_cutoff(label,cutoff,is_blind):
    cut=v6.iso_ms(cutoff); btc_source,btc_frames,btc_sums=v6.load_frames("BTC",cut); results=[]
    for sym in v6.COINS:
        try:
            source,frames,sums=(btc_source,btc_frames,btc_sums) if sym=="BTC" else v6.load_frames(sym,cut)
            deriv=derivatives_snapshot(sym,cut)
            sc,model=final_score(sym,sums,frames,btc_frames,btc_sums,deriv)
            side="BUY" if sc>=0 else "SELL"; entry=frames["M5"][-1]["close"]
            sl,tp,rr,bar=choose_barriers(sym,side,entry,sums,frames,model,sc)
            out=v6.evaluate(source,sym,side,entry,sl,tp,cut)
            results.append({"symbol":sym+"USDT","cutoff":cutoff,"source":source,"blind":is_blind,"decision":side,"score":round(sc,3),"entry":entry,"sl":sl,"tp":tp,"plannedRR":round(rr,3),"barrier":bar,"model":model,"outcome":out})
        except Exception as e: results.append({"symbol":sym+"USDT","cutoff":cutoff,"error":str(e)})
    usable=[r for r in results if r.get("decision") in ("BUY","SELL")]; resolved=[r for r in usable if r.get("outcome",{}).get("result") in ("TP","SL")]
    wins=[r for r in resolved if r["outcome"]["result"]=="TP"]; losses=[r for r in resolved if r["outcome"]["result"]=="SL"]
    total=sum(r["plannedRR"] if r["outcome"]["result"]=="TP" else -1 for r in resolved)
    s={"label":label,"cutoff":cutoff,"isTrueBlind":is_blind,"requested":len(v6.COINS),"marketTrades":len(usable),"dataErrors":len(results)-len(usable),"resolved":len(resolved),"wins":len(wins),"losses":len(losses),"unresolved":len(usable)-len(resolved),"winRateResolved":round(100*len(wins)/len(resolved),2) if resolved else None,"avgPlannedRR":round(sum(r["plannedRR"] for r in resolved)/len(resolved),3) if resolved else None,"expectancyR":round(total/len(resolved),3) if resolved else None}
    return {"summary":s,"tests":results}

def main():
    samples={label:run_cutoff(label,cutoff,b) for label,cutoff,b in CUTOFFS}
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"V10 derivatives-aware forced-market: V6 regime/structure + multi-TF coherence + pre-cutoff Bybit OI/funding/long-short context. Free SL from nearest structural pivot with coin-volatility ATR floor/cap. TP is nearest M15/H1 liquidity beyond confidence/regime-specific minimum RR (1.25-2.10), capped for realism. No WAIT/LIMIT. Future hidden until decision.","samples":samples}
    with open("data/blind_backtest_v10.json","w") as f: json.dump(payload,f,indent=2)
    print(json.dumps({k:v["summary"] for k,v in samples.items()},indent=2))
if __name__=="__main__": main()
