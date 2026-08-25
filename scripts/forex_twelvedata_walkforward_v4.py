#!/usr/bin/env python3
import os,json,math,random,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,timezone
from collections import defaultdict

KEY=os.environ.get("TWELVEDATA_API_KEY","").strip()
if not KEY: raise SystemExit("TWELVEDATA_API_KEY missing")
OUT="data/forex-twelvedata-walkforward-latest.json"
SYMS=["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","NZD/USD","USD/CAD","EUR/JPY","GBP/JPY","EUR/GBP","XAU/USD"]
SEED=int(os.environ.get("BACKTEST_SEED") or random.SystemRandom().randrange(1,2**31-1))
RNG=random.Random(SEED)
WINDOWS=int(os.environ.get("BACKTEST_WINDOWS","6"))
DAYS=int(os.environ.get("BACKTEST_WINDOW_DAYS","24"))
MIN_TRADES=int(os.environ.get("BACKTEST_MIN_TEST_DAYS","18"))
TARGET=float(os.environ.get("BACKTEST_TARGET_WR","80"))
SOURCE_SHA=os.environ.get("GITHUB_SHA","")
START=datetime(2025,1,6,tzinfo=timezone.utc)
END=datetime(2026,7,31,tzinfo=timezone.utc)
HOURS=(6,7,8,9,10,12,13,14,15,16)
STOPS=(0.8,1.0,1.2,1.5,1.8,2.2)
RRS=(1,2)
MIN_PROB={1:float(os.environ.get("RR1_MIN_PROB","0.74")),2:float(os.environ.get("RR2_MIN_PROB","0.72"))}
MIN_LOCAL={1:float(os.environ.get("RR1_MIN_LOCAL","0.86")),2:float(os.environ.get("RR2_MIN_LOCAL","0.86"))}

def f(x,d=0.0):
    try:return float(x)
    except:return d

def ema(xs,p):
    if not xs:return []
    k=2/(p+1);out=[];e=xs[0]
    for x in xs:
        e=x*k+e*(1-k);out.append(e)
    return out

def atr(rows,p=14):
    out=[0.0]*len(rows);trs=[]
    for i,r in enumerate(rows):
        tr=r["h"]-r["l"] if i==0 else max(r["h"]-r["l"],abs(r["h"]-rows[i-1]["c"]),abs(r["l"]-rows[i-1]["c"]))
        trs.append(tr);out[i]=sum(trs[max(0,i-p+1):i+1])/min(p,i+1)
    return out

def rsi(cs,p=14):
    out=[50.0]*len(cs);g=[];l=[]
    for i in range(1,len(cs)):
        d=cs[i]-cs[i-1];g.append(max(d,0));l.append(max(-d,0))
        if i>=p:
            ga=sum(g[i-p:i])/p;lo=sum(l[i-p:i])/p
            out[i]=100 if lo==0 else 100-100/(1+ga/lo)
    return out

def fetch(sym,a,b):
    q=urllib.parse.urlencode({"symbol":sym,"interval":"5min","start_date":a.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date":b.strftime("%Y-%m-%d %H:%M:%S"),"outputsize":5000,"timezone":"UTC","apikey":KEY})
    url="https://api.twelvedata.com/time_series?"+q;err=None
    for attempt in range(5):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"TradingProjectWalkForward/4.0","Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
            j=json.loads(raw.decode("utf-8"))
            if j.get("status")=="error" or "values" not in j: raise RuntimeError(f"{sym}: {j}")
            rows=[]
            for x in reversed(j["values"]):
                rows.append({"t":datetime.strptime(x["datetime"],"%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
                    "o":f(x["open"]),"h":f(x["high"]),"l":f(x["low"]),"c":f(x["close"])})
            return rows
        except Exception as e:
            err=e;time.sleep(3*(attempt+1))
    raise RuntimeError(f"{sym} TwelveData failed after retries: {err}")

def enrich(rows):
    cs=[x["c"] for x in rows];e8=ema(cs,8);e20=ema(cs,20);e50=ema(cs,50);aa=atr(rows,14);rr=rsi(cs,14)
    for i,x in enumerate(rows):x.update(e8=e8[i],e20=e20[i],e50=e50[i],atr=aa[i],rsi=rr[i])
    return rows

def day_groups(rows):
    g=defaultdict(list)
    for r in rows:g[r["t"].date().isoformat()].append(r)
    return {k:v for k,v in g.items() if len(v)>=120}

def idx_for_hour(rows,h):
    for i,r in enumerate(rows):
        if r["t"].hour==h and i>=48:return i
    return None

def features(rows,i,side,stop,rr):
    r=rows[i];a=max(r["atr"],1e-12);c=r["c"];p3=rows[max(0,i-3)]["c"];p12=rows[max(0,i-12)]["c"];p36=rows[max(0,i-36)]["c"]
    past=rows[:i+1];hi=max(x["h"] for x in past);lo=min(x["l"] for x in past);pos=(c-lo)/max(hi-lo,1e-12)
    body=abs(r["c"]-r["o"])/a;bar_range=(r["h"]-r["l"])/a
    return [
        side*(r["e8"]-r["e20"])/a,side*(r["e20"]-r["e50"])/a,
        side*(c-p3)/a,side*(c-p12)/a,side*(c-p36)/a,
        side*(r["rsi"]-50)/25,side*(c-r["e20"])/a,(pos-.5)*side*2,
        min(3.0,a/max(abs(c),1e-12)*10000)/3,min(2.5,body)/2.5,min(3.5,bar_range)/3.5,
        math.sin(2*math.pi*r["t"].hour/24),math.cos(2*math.pi*r["t"].hour/24),
        (stop-1.5)/0.8,(rr-1.5)/.5
    ]

def outcome(rows,i,side,stop,rr):
    r=rows[i];dist=max(r["atr"]*stop,1e-12);entry=r["c"];sl=entry-side*dist;tp=entry+side*dist*rr;mfe=mae=0.0
    for z in rows[i+1:]:
        fav=z["h"]-entry if side>0 else entry-z["l"];adv=entry-z["l"] if side>0 else z["h"]-entry
        mfe=max(mfe,fav/dist);mae=max(mae,adv/dist)
        hs=z["l"]<=sl if side>0 else z["h"]>=sl;ht=z["h"]>=tp if side>0 else z["l"]<=tp
        if hs and ht:return 0,-1.0,mfe,mae,"SL_SAME_BAR_PESSIMISTIC"
        if hs:return 0,-1.0,mfe,mae,"SL"
        if ht:return 1,float(rr),mfe,mae,"TP"
    return 0,-1.0,mfe,mae,"TIMEOUT_AS_LOSS"

def samples_for_day(rows):
    s=[]
    for h in HOURS:
        i=idx_for_hour(rows,h)
        if i is None:continue
        for side in (-1,1):
            for stop in STOPS:
                for rr in RRS:
                    y,r,mfe,mae,why=outcome(rows,i,side,stop,rr)
                    s.append({"x":features(rows,i,side,stop,rr),"y":y,"r":r,"h":h,"side":side,"stop":stop,"rr":rr})
    return s

def dist(a,b):
    weights=(1.2,1.2,.65,.95,.8,.75,.9,.55,.25,.25,.2,.15,.15,.55,.7)
    return sum(w*(x-y)*(x-y) for w,x,y in zip(weights,a,b))

def predict(x,train,k=25):
    ds=sorted(((dist(x,z["x"]),z["y"]) for z in train),key=lambda q:q[0])[:min(k,len(train))]
    if not ds:return .5,.5,0
    num=1.5;den=3.0
    for d,y in ds:
        w=1/(0.06+d);num+=w*y;den+=w
    p=num/den
    local=sum(y for _,y in ds[:min(7,len(ds))])/min(7,len(ds))
    return p,local,len(ds)

def regime_ok(x,rr):
    trend1=x[0];trend2=x[1];mom3=x[2];mom12=x[3];rsi_side=x[5];extension=abs(x[6])
    strong=(trend1>0.08 and trend2>0.05 and mom12>0.02 and rsi_side>0.08)
    impulse=(mom3>-0.20 and extension<1.35)
    if rr==2:strong=strong and (trend1+trend2>0.24) and mom12>0.08
    return strong and impulse

def choose_trade(rows,train,forced_rr):
    candidates=[]
    for h in HOURS:
        i=idx_for_hour(rows,h)
        if i is None:continue
        for side in (-1,1):
            for stop in STOPS:
                x=features(rows,i,side,stop,forced_rr)
                if not regime_ok(x,forced_rr):continue
                pr,local,n=predict(x,train)
                edge=pr*(forced_rr+1)-1
                quality=edge+.07*x[0]+.08*x[1]+.04*x[3]-.025*abs(x[6])
                candidates.append((quality,pr,local,n,i,side,stop,x))
    if not candidates:return None,"NO_REGIME_CANDIDATE"
    quality,pr,local,n,i,side,stop,x=max(candidates,key=lambda q:q[0])
    if pr<MIN_PROB[forced_rr] or local<MIN_LOCAL[forced_rr]:
        return None,f"CONFIDENCE_GATE pr={pr:.3f} local={local:.3f}"
    y,r,mfe,mae,why=outcome(rows,i,side,stop,forced_rr);e=rows[i]
    return {"day":e["t"].date().isoformat(),"entry_time":e["t"].isoformat(),"side":"BUY" if side>0 else "SELL",
        "rr":forced_rr,"stopAtr":stop,"predictedWinProb":round(pr,4),"localConsensus":round(local,4),
        "modelEdge":round(pr*(forced_rr+1)-1,4),"quality":round(quality,4),
        "result":"WIN" if y else "LOSS","r":r,"mfeR":round(mfe,3),"maeR":round(mae,3),"exitReason":why},None

def metrics(ts):
    n=len(ts);w=sum(x["result"]=="WIN" for x in ts)
    return {"trades":n,"wins":w,"losses":n-w,"winrate":round(100*w/n,2) if n else 0,
        "avgR":round(sum(x["r"] for x in ts)/n,3) if n else 0}

def random_windows():
    span=(END-START).days-DAYS;chosen=[];attempts=0
    while len(chosen)<WINDOWS and attempts<20000:
        attempts+=1;a=START+timedelta(days=RNG.randint(0,max(1,span)));b=a+timedelta(days=DAYS)
        if any(not (b<=x or a>=y) for x,y in chosen):continue
        chosen.append((a,b))
    if len(chosen)<WINDOWS:raise RuntimeError(f"could not sample {WINDOWS} non-overlapping windows")
    return sorted(chosen,key=lambda z:z[0])

windows=random_windows()
report={"version":"FOREX-TWELVEDATA-WALKFORWARD-4-SELECTIVE","sourceSha":SOURCE_SHA,"seed":SEED,
    "generatedAt":datetime.now(timezone.utc).isoformat(),
    "rules":{"source":"Twelve Data 5min","noLookahead":True,"learner":"per-symbol expanding selective KNN",
        "sameBarSLTP":"SL_FIRST_PESSIMISTIC","timeouts":"LOSS","rrEvaluatedIndependently":[1,2],
        "allowNoTrade":True,"selectionGate":{"rr1MinProb":MIN_PROB[1],"rr2MinProb":MIN_PROB[2],
        "rr1MinLocalConsensus":MIN_LOCAL[1],"rr2MinLocalConsensus":MIN_LOCAL[2]},
        "randomWindowsNonOverlappingWithinRound":True,"targetWinratePctStrictlyGreaterThanPerSymbolPerRR":TARGET,
        "minimumTestTradesPerSymbolPerRR":MIN_TRADES,
        "holdout":"60% prefix trains; 40% suffix is sequential OOS; a closed OOS day may enter training only after its decisions are recorded",
        "antiCherryPick":"NO TRADE is decided before outcome from model/regime confidence only; all accepted trades, abstentions, windows and failures are persisted; every symbol must pass both RR profiles"},
    "windows":[{"start":a.isoformat(),"end":b.isoformat()} for a,b in windows],"symbols":{},"pass":False}

allpass=True
for sym in SYMS:
    trades=[];source=[];data_error=None
    try:
        for wi,(a,b) in enumerate(windows):
            rows=enrich(fetch(sym,a,b));g=day_groups(rows);days=sorted(g);cut=max(3,int(len(days)*.60));tr=days[:cut];te=days[cut:];train=[]
            for d in tr:train.extend(samples_for_day(g[d]))
            wintr=[];abstain={"1":0,"2":0};reasons=defaultdict(int)
            for d in te:
                for forced_rr in RRS:
                    t,reason=choose_trade(g[d],train,forced_rr)
                    if t:trades.append(t);wintr.append(t)
                    else:
                        abstain[str(forced_rr)]+=1;reasons[reason]+=1
                train.extend(samples_for_day(g[d]))
            source.append({"window":wi,"bars":len(rows),"trainDays":len(tr),"testDays":len(te),
                "acceptedTrades":len(wintr),"abstentionsByRR":abstain,"abstentionReasons":dict(reasons),
                "testMetrics":{"all":metrics(wintr),"RR1":metrics([x for x in wintr if x["rr"]==1]),"RR2":metrics([x for x in wintr if x["rr"]==2])}})
            time.sleep(8.2)
    except Exception as e:data_error=str(e)
    by_rr={str(rr):metrics([x for x in trades if x["rr"]==rr]) for rr in RRS}
    rr_pass={str(rr):(data_error is None and by_rr[str(rr)]["trades"]>=MIN_TRADES and
        by_rr[str(rr)]["winrate"]>TARGET and by_rr[str(rr)]["avgR"]>0) for rr in RRS}
    passed=all(rr_pass.values())
    report["symbols"][sym.replace("/","")]={"pass":passed,"rrPass":rr_pass,"holdout":{"all":metrics(trades),"byRR":by_rr},
        "source":source,"dataError":data_error,"trades":trades}
    allpass &= passed
    print(sym,by_rr,"PASS" if passed else "FAIL",data_error or "",flush=True)
    report["pass"]=False;os.makedirs(os.path.dirname(OUT),exist_ok=True)
    with open(OUT,"w") as fh:json.dump(report,fh,indent=2)
report["pass"]=allpass
with open(OUT,"w") as fh:json.dump(report,fh,indent=2)
print("FINAL_PASS",allpass,"seed",SEED)
