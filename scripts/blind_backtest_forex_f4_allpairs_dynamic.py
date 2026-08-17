#!/usr/bin/env python3
import json, math, os, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PAIRS=[
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
CCY=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
CUTS=["2026-06-26T08:00:00Z","2026-07-06T08:00:00Z","2026-07-09T08:00:00Z","2026-07-20T08:00:00Z","2026-07-28T08:00:00Z"]
END_DATE="2026-07-29 08:00:00"; OUTPUTSIZE=5000
TRADE_H=24; LIMIT_H=4

def DT(s): return datetime.fromisoformat(s.replace("Z","+00:00"))
def ema(v,n):
    if not v:return None
    a=2/(n+1); x=v[0]
    for z in v[1:]: x=a*z+(1-a)*x
    return x

def rsi(v,n=14):
    if len(v)<n+1:return None
    d=[b-a for a,b in zip(v[-n-1:-1],v[-n:])]
    g=sum(max(x,0) for x in d)/n; l=sum(max(-x,0) for x in d)/n
    return 100 if l==0 else 100-100/(1+g/l)
def atr(rows,n=14):
    if len(rows)<n+1:return None
    x=rows[-n-1:]; tr=[]
    for i in range(1,len(x)):
        p=x[i-1]["close"]; q=x[i]
        tr.append(max(q["high"]-q["low"],abs(q["high"]-p),abs(q["low"]-p)))
    return sum(tr)/len(tr)
def adx(rows,n=14):
    if len(rows)<2*n+2:return None
    x=rows[-(2*n+2):]; trs=[]; pds=[]; mds=[]
    for i in range(1,len(x)):
        p=x[i-1]; q=x[i]
        up=q["high"]-p["high"]; dn=p["low"]-q["low"]
        pds.append(up if up>dn and up>0 else 0); mds.append(dn if dn>up and dn>0 else 0)
        trs.append(max(q["high"]-q["low"],abs(q["high"]-p["close"]),abs(q["low"]-p["close"])))
    dx=[]
    for i in range(n,len(trs)+1):
        tr=sum(trs[i-n:i]); pd=sum(pds[i-n:i]); md=sum(mds[i-n:i])
        if tr<=0:continue
        pdi=100*pd/tr; mdi=100*md/tr; den=pdi+mdi
        dx.append(100*abs(pdi-mdi)/den if den else 0)
    return sum(dx[-n:])/len(dx[-n:]) if dx else None
def bucket(t,h): return t.replace(hour=(t.hour//h)*h,minute=0,second=0,microsecond=0)
def agg(rows,h):
    d=defaultdict(list); need=h*4
    for r in rows:d[bucket(r["dt"],h)].append(r)
    out=[]
    for t in sorted(d):
        g=d[t]
        if len(g)<max(1,need-1):continue
        out.append({"dt":t,"open":g[0]["open"],"high":max(x["high"] for x in g),"low":min(x["low"] for x in g),"close":g[-1]["close"]})
    return out
def before(rows,t):
    x=None
    for r in rows:
        if r["dt"]<=t:x=r["close"]
        else:break
    return x
def zmap(d):
    if len(d)<2:return {k:0 for k in d}
    m=statistics.mean(d.values()); s=statistics.pstdev(d.values())
    return {k:(v-m)/s if s>1e-12 else 0 for k,v in d.items()}
def parse_batch(p):
    out={}
    if isinstance(p,dict) and "values" not in p:
        for k,v in p.items():
            if not isinstance(v,dict):continue
            q=v.get("data") if isinstance(v.get("data"),dict) else v
            if isinstance(q,dict) and q.get("values"):
                s=((q.get("meta") or {}).get("symbol") or k).replace("/","").upper(); out[s]=q
    return out

def fetch():
    key=os.environ.get("TWELVEDATA_API_KEY","").strip()
    if not key: raise RuntimeError("TWELVEDATA_API_KEY missing")
    out={}; groups=[PAIRS[i:i+7] for i in range(0,28,7)]
    for i,g in enumerate(groups):
        syms=",".join(f"{p[:3]}/{p[3:]}" for p in g)
        qs=urllib.parse.urlencode({"symbol":syms,"interval":"15min","outputsize":OUTPUTSIZE,"end_date":END_DATE,"timezone":"UTC","order":"asc","apikey":key})
        req=urllib.request.Request("https://api.twelvedata.com/time_series?"+qs,headers={"User-Agent":"trading-api-forex-f4/1.0"})
        with urllib.request.urlopen(req,timeout=100) as z:p=json.loads(z.read().decode())
        got=parse_batch(p); miss=[x for x in g if x not in got]
        if miss:raise RuntimeError(f"batch {i+1} missing {miss}: {str(p)[:1500]}")
        out.update(got); print(f"Fetched {i+1}/4: {','.join(g)}")
        if i<3: time.sleep(66)
    return out

def norm(x):
    o=[]
    for r in x["values"]:
        t=datetime.fromisoformat(r["datetime"]).replace(tzinfo=timezone.utc)
        o.append({"dt":t,"open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"])})
    return sorted(o,key=lambda q:q["dt"])

def strength(frames,cut):
    hs=[6,24,72]; raw={h:{} for h in hs}
    for p,rows in frames.items():
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre:continue
        now=pre[-1]["close"]
        for h in hs:
            old=before(pre,cut-timedelta(hours=h))
            if old and old>0:raw[h][p]=math.log(now/old)
    zz={h:zmap(raw[h]) for h in hs}; ans={h:{c:[] for c in CCY} for h in hs}
    for h in hs:
        for p,v in zz[h].items():
            b,q=p[:3],p[3:]; ans[h][b].append(v); ans[h][q].append(-v)
    return {h:{c:(statistics.mean(v) if v else 0) for c,v in ans[h].items()} for h in hs}

def feature(pair,rows,cut,st):
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<450:return None
    h1=agg(pre,1); h4=agg(pre,4)
    if len(h1)<80 or len(h4)<55:return None
    c=pre[-1]["close"]; a=atr(pre); hc=[x["close"] for x in h1]; q4=[x["close"] for x in h4]; mc=[x["close"] for x in pre]
    if not a:return None
    e4=ema(q4[-100:],20); e450=ema(q4[-140:],50); e1=ema(hc[-100:],20); e150=ema(hc[-140:],50); em=ema(mc[-100:],20)
    er=rsi(hc); ax=adx(h1)
    if None in (e4,e450,e1,e150,em,er,ax):return None
    b,q=pair[:3],pair[3:]; d6=st[6][b]-st[6][q]; d24=st[24][b]-st[24][q]; d72=st[72][b]-st[72][q]
    s4=1 if c>e4>e450 else -1 if c<e4<e450 else (1 if c>e4 else -1)
    s1=1 if c>e1>e150 else -1 if c<e1<e150 else (1 if c>e1 else -1)
    m4=(c-mc[-5])/a
    sm=1 if c>em and m4>=0 else -1 if c<em and m4<=0 else (1 if c>em else -1)
    score=1.20*d6+.80*d24+.45*d72+1.15*s4+.95*s1+.45*sm
    # Currency-specific direction stabilizers without adding more indicators.
    if "JPY" in (b,q): score += .15*s4
    if "CHF" in (b,q): score += .10*s1
    if "CAD" in (b,q): score += .10*sm
    side="BUY" if score>=0 else "SELL"; sg=1 if side=="BUY" else -1
    recent=pre[-12:]
    swing=min(x["low"] for x in recent) if side=="BUY" else max(x["high"] for x in recent)
    base=(c-swing) if side=="BUY" else (swing-c)
    # Dynamic structural stop: local invalidation plus volatility buffer; no universal RR.
    buffer=(.12 if ax>=25 else .18)*a
    risk=max(base+buffer,.85*a)
    # High-volatility/carry currencies get modestly wider floor.
    if "JPY" in (b,q) or "GBP" in (b,q):risk=max(risk,1.0*a)
    sl=c-risk if side=="BUY" else c+risk
    agree=sum((x*sg)>0 for x in (d6,d24,d72))
    chase=abs(c-em)/a
    stretched=(er>68 if side=="BUY" else er<32)
    # Dynamic target geometry from trend quality + volatility + known pre-cutoff structure.
    rr=1.15 + .22*agree + (.28 if ax>=25 else .10 if ax>=18 else -.10) + (.18 if s4==sg and s1==sg else -.12) + (.12 if chase<.55 else -.10) - (.25 if stretched else 0)
    rr=max(.90,min(2.60,rr))
    prior_high=max(x["high"] for x in h1[-24:]); prior_low=min(x["low"] for x in h1[-24:])
    struct_dist=(prior_high-c) if side=="BUY" else (c-prior_low)
    if struct_dist>0:
        struct_rr=struct_dist/risk
        if .80<=struct_rr<=3.2: rr=min(rr,max(.85,struct_rr))
    tp=c+risk*rr if side=="BUY" else c-risk*rr
    # LIMIT only changes execution, thesis SL/TP stay frozen for fair comparison.
    if side=="BUY": lim=max(sl+.10*risk, min(c-.18*risk, em if em<c else c-.18*risk))
    else: lim=min(sl-.10*risk, max(c+.18*risk, em if em>c else c+.18*risk))
    return {"symbol":pair,"side":side,"entry":c,"limit":lim,"sl":sl,"tp":tp,"risk":risk,"rr":rr,"score":score,"adx":ax,"rsi":er,"d6":d6,"d24":d24,"d72":d72,"agree":agree,"chaseATR":chase}

def direction_eval(f,rows,cut):
    sg=1 if f["side"]=="BUY" else -1; en=f["entry"]; out={}
    for h in (6,12,24):
        close=before(rows,cut+timedelta(hours=h))
        out[str(h)+"h"]={"close":close,"correct":((close-en)*sg>0) if close is not None else None,"returnPct":((close/en-1)*100*sg) if close else None}
    return out

def market_eval(f,rows,cut):
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_H)]
    side=f["side"]; sl=f["sl"]; tp=f["tp"]; en=f["entry"]; sg=1 if side=="BUY" else -1
    mfe=0; mae=0
    for i,r in enumerate(fut,1):
        fav=(r["high"]-en) if side=="BUY" else (en-r["low"]); adv=(en-r["low"]) if side=="BUY" else (r["high"]-en)
        mfe=max(mfe,fav/f["risk"]); mae=max(mae,adv/f["risk"])
        hit_sl=r["low"]<=sl if side=="BUY" else r["high"]>=sl; hit_tp=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if hit_sl and hit_tp:return {"result":"AMBIGUOUS","bars":i,"mfeR":mfe,"maeR":mae}
        if hit_sl:return {"result":"SL","bars":i,"mfeR":mfe,"maeR":mae}
        if hit_tp:return {"result":"TP","bars":i,"mfeR":mfe,"maeR":mae}
    return {"result":"TIMEOUT","bars":len(fut),"mfeR":mfe,"maeR":mae}
def limit_eval(f,rows,cut):
    side=f["side"]; lim=f["limit"]; sl=f["sl"]; tp=f["tp"]
    fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_H)]; fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_H):break
        tgt=r["high"]>=tp if side=="BUY" else r["low"]<=tp; fill=r["low"]<=lim if side=="BUY" else r["high"]>=lim
        if tgt and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False}
    lr=abs(lim-sl); eff=abs(tp-lim)/lr if lr else None; mfe=0; mae=0
    for j,r in enumerate(fut[fi:],1):
        fav=(r["high"]-lim) if side=="BUY" else (lim-r["low"]); adv=(lim-r["low"]) if side=="BUY" else (r["high"]-lim)
        mfe=max(mfe,fav/lr if lr else 0); mae=max(mae,adv/lr if lr else 0)
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl; b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:return {"result":"AMBIGUOUS","filled":True,"effectiveRR":eff,"bars":j,"mfeR":mfe,"maeR":mae}
        if a:return {"result":"SL","filled":True,"effectiveRR":eff,"bars":j,"mfeR":mfe,"maeR":mae}
        if b:return {"result":"TP","filled":True,"effectiveRR":eff,"bars":j,"mfeR":mfe,"maeR":mae}
    return {"result":"TIMEOUT","filled":True,"effectiveRR":eff,"bars":len(fut)-fi,"mfeR":mfe,"maeR":mae}

def summarize(rows,key):
    outs=[x[key] for x in rows]; res=[o for o in outs if o["result"] in ("TP","SL")]; w=sum(o["result"]=="TP" for o in res); l=len(res)-w
    if key=="market":
        ex=sum((rows[i]["feature"]["rr"] if o["result"]=="TP" else -1) for i,o in enumerate(outs) if o["result"] in ("TP","SL"))
    else:
        ex=sum((o.get("effectiveRR",0) if o["result"]=="TP" else -1) for o in outs if o["result"] in ("TP","SL"))
    return {"signals":len(outs),"resolved":len(res),"wins":w,"losses":l,"winRateResolved":round(100*w/len(res),2) if res else None,"expectancyR":round(ex/len(res),3) if res else None,"timeouts":sum(o["result"]=="TIMEOUT" for o in outs),"ambiguous":sum(o["result"]=="AMBIGUOUS" for o in outs),"noFill":sum(o["result"]=="NO_FILL" for o in outs),"targetBeforeFill":sum(o["result"]=="TARGET_BEFORE_FILL" for o in outs)}
def dirsum(rows,h):
    vals=[x["direction"][h]["correct"] for x in rows if x["direction"][h]["correct"] is not None]
    return {"n":len(vals),"correct":sum(vals),"accuracy":round(100*sum(vals)/len(vals),2) if vals else None}
def by_symbol(rows):
    out={}
    for p in PAIRS:
        g=[x for x in rows if x["feature"]["symbol"]==p]; out[p]={"market":summarize(g,"market"),"limit":summarize(g,"limit"),"direction6h":dirsum(g,"6h"),"direction12h":dirsum(g,"12h"),"direction24h":dirsum(g,"24h")}
    return out

def main():
    raw=fetch(); frames={p:norm(raw[p]) for p in PAIRS}; allrows=[]; bycut={}
    for cs in CUTS:
        cut=DT(cs); st=strength(frames,cut); block=[]
        for p in PAIRS:
            f=feature(p,frames[p],cut,st)
            if not f:continue
            row={"cutoff":cs,"feature":f,"direction":direction_eval(f,frames[p],cut),"market":market_eval(f,frames[p],cut),"limit":limit_eval(f,frames[p],cut)}
            block.append(row); allrows.append(row)
        bycut[cs]={"n":len(block),"market":summarize(block,"market"),"limit":summarize(block,"limit"),"direction6h":dirsum(block,"6h"),"direction12h":dirsum(block,"12h"),"direction24h":dirsum(block,"24h")}
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"method":"FOREX F4 forced all-pair blind benchmark. Every valid pair receives BUY or SELL. Direction uses 6h/24h/72h cross-currency strength plus H4/H1 EMA structure and minimal RSI/ADX/ATR context. SL is structural plus volatility buffer. TP is dynamic from trend agreement, ADX, chase/exhaustion and pre-cutoff H1 structure; no universal RR. LIMIT uses a pre-known M15 EMA/value pullback when favorable, otherwise an 0.18R pullback; same frozen thesis SL/TP as MARKET. Also evaluates direction accuracy at 6h/12h/24h, MFE/MAE. No historical macro/news reconstruction is used, avoiding hindsight.","integrity":{"rulesFrozenBeforeOutcomes":True,"forcedAllPairs":True,"noTop3":True,"noNoTrade":True,"lookAheadDecision":False},"dataPlan":{"provider":"Twelve Data","intervalFetched":"15min","pairs":28,"creditsExpected":28,"outputsize":OUTPUTSIZE,"rawCommitted":False},"cutoffs":CUTS,"summary":{"signals":len(allrows),"market":summarize(allrows,"market"),"limit":summarize(allrows,"limit"),"direction6h":dirsum(allrows,"6h"),"direction12h":dirsum(allrows,"12h"),"direction24h":dirsum(allrows,"24h"),"avgPlannedRR":round(statistics.mean(x["feature"]["rr"] for x in allrows),3)},"byCutoff":bycut,"bySymbol":by_symbol(allrows),"trades":allrows}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f4_allpairs_dynamic.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({"summary":result["summary"],"byCutoff":bycut,"bySymbol":result["bySymbol"]},indent=2))
if __name__=="__main__":main()
