#!/usr/bin/env python3
import glob, json, math, os, statistics
from collections import defaultdict

PAIR_SET={
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"}

FILES=[
    "data/blind_backtest_forex_f4.json",
    "data/blind_backtest_forex_f5_horizon.json",
    "data/blind_backtest_forex_f6.json",
    "data/blind_backtest_forex_f6_dual_horizon.json",
]

def walk(x,path=""):
    if isinstance(x,dict):
        yield path,x
        for k,v in x.items():
            yield from walk(v, path+"/"+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,path+f"/{i}")

def num(x,k,default=None):
    v=x.get(k,default) if isinstance(x,dict) else default
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) else default

def market_score(m):
    exp=num(m,"expectancyR",-9); wr=num(m,"winRateResolved",0); rr=num(m,"avgPlannedRR",num(m,"avgRR",0))
    return 1.8*exp + 0.008*(wr-40) + 0.03*min(rr,2.5)

def table_score(path, table, filename):
    # Prefer true holdout/output tables, reject development/model-selection tables.
    p=path.lower(); s=0
    if len([k for k in table if k in PAIR_SET])>=20: s+=10
    for bad in ("pairmodelselection","development","models","selection"):
        if bad in p: s-=20
    for good in ("validation","holdout","bysymbol","bypair","sameholdout"):
        if good in p: s+=2
    if "f6.json" in filename:
        if "baselinef5" in p: s-=4
        if "f6" in p or "rotation" in p: s+=3
    return s

def dir_metric(d):
    if not isinstance(d,dict): return None
    acc=num(d,"accuracy")
    n=num(d,"n",num(d,"tests"))
    return (acc,n) if acc is not None and n else None

def extract_canonical_pair_table(data, filename):
    cand=[]
    for path,d in walk(data):
        if not isinstance(d,dict): continue
        keys=[k for k in d if k in PAIR_SET]
        if len(keys)<20: continue
        valid=sum(1 for k in keys if isinstance(d[k],dict) and isinstance(d[k].get("market"),dict))
        if valid<20: continue
        cand.append((table_score(path,d,filename),path,d))
    if not cand: return None,None
    cand.sort(key=lambda z:(z[0],len(z[1])),reverse=True)
    return cand[0][1],cand[0][2]

def extract_forced_summaries(data):
    out=[]
    for path,d in walk(data):
        if not isinstance(d,dict): continue
        m=d.get("market")
        if not isinstance(m,dict): continue
        sig=num(m,"signals",num(d,"signals",0)) or 0
        if sig < 100: continue
        if any(b in path.lower() for b in ("development","pairmodelselection","models")): continue
        out.append((path,d))
    # dedupe identical market tuples within file
    seen=set(); z=[]
    for p,d in out:
        m=d["market"]
        key=(num(m,"signals"),num(m,"wins"),num(m,"losses"),num(m,"expectancyR"))
        if key in seen: continue
        seen.add(key);z.append((p,d))
    return z

def main():
    sources=[]; pair_runs=defaultdict(list); forced=[]
    for fn in FILES:
        if not os.path.exists(fn): continue
        with open(fn,"r",encoding="utf-8") as f:data=json.load(f)
        path,table=extract_canonical_pair_table(data,fn)
        src={"file":fn,"canonicalPairTablePath":path}
        for p,d in extract_forced_summaries(data):
            m=d["market"]; l=d.get("limit") if isinstance(d.get("limit"),dict) else None
            rec={"file":fn,"path":p,"market":m}
            if l: rec["limit"]=l
            for dk in ("direction3","direction6","direction8","direction12","direction24","chosenDirection"):
                if dk in d: rec[dk]=d[dk]
            forced.append(rec)
        if table:
            for sym in sorted(PAIR_SET):
                d=table.get(sym)
                if not isinstance(d,dict) or not isinstance(d.get("market"),dict): continue
                rec={"source":fn,"path":path,"market":d["market"]}
                if isinstance(d.get("limit"),dict): rec["limit"]=d["limit"]
                for dk in ("direction3","direction6","direction8","direction12","direction24","chosenDirection","dir12","dir24"):
                    if dk in d: rec[dk]=d[dk]
                pair_runs[sym].append(rec)
        sources.append(src)

    # Source-level robust comparison: only one most representative forced summary per file.
    source_best=[]
    for fn in FILES:
        rows=[r for r in forced if r["file"]==fn]
        if not rows: continue
        # prefer root/summary-like shortest path, except f6 baseline if another method block exists
        rows.sort(key=lambda r:("baseline" in r["path"].lower(), len(r["path"])))
        r=rows[0]
        source_best.append({"file":fn,"path":r["path"],"market":r["market"],"limit":r.get("limit"),
                            **{k:r[k] for k in r if k.startswith("direction") or k=="chosenDirection"}})

    pair_meta={}
    for sym,runs in pair_runs.items():
        exps=[]; wrs=[]; pos=0; dirs=[]; dir24=[]; dir3=[]
        for r in runs:
            m=r["market"]
            e=num(m,"expectancyR"); w=num(m,"winRateResolved")
            if e is not None: exps.append(e); pos+=1 if e>0 else 0
            if w is not None: wrs.append(w)
            for k,v in r.items():
                if k.startswith("direction") or k in ("chosenDirection","dir12","dir24"):
                    dm=dir_metric(v)
                    if dm: dirs.append(dm[0])
            for k in ("direction24","dir24"):
                dm=dir_metric(r.get(k));
                if dm: dir24.append(dm[0])
            dm=dir_metric(r.get("direction3"));
            if dm: dir3.append(dm[0])
        n=len(exps)
        medexp=statistics.median(exps) if exps else None
        meanexp=statistics.mean(exps) if exps else None
        meanwr=statistics.mean(wrs) if wrs else None
        consistency=pos/n if n else 0
        # conservative grade rewards repeated positive expectancy, not one lucky block.
        robust=(0 if medexp is None else medexp) + 0.20*(consistency-0.5) + (0 if meanwr is None else (meanwr-40)/250)
        if n>=3 and consistency>=0.67 and medexp is not None and medexp>0: grade="ROBUST_POSITIVE"
        elif n>=2 and consistency>=0.5 and medexp is not None and medexp>=0: grade="WATCH_POSITIVE"
        elif n>=2 and consistency<=0.34 and medexp is not None and medexp<0: grade="WEAK_REWORK"
        else: grade="MIXED"
        pair_meta[sym]={
            "blocks":n,"positiveExpectancyBlocks":pos,"positiveRate":round(consistency,3),
            "medianExpectancyR":None if medexp is None else round(medexp,3),
            "meanExpectancyR":None if meanexp is None else round(meanexp,3),
            "meanResolvedWR":None if meanwr is None else round(meanwr,2),
            "meanDirectionAccuracy":None if not dirs else round(statistics.mean(dirs),2),
            "meanDirection3h":None if not dir3 else round(statistics.mean(dir3),2),
            "meanDirection24h":None if not dir24 else round(statistics.mean(dir24),2),
            "robustScore":round(robust,3),"grade":grade,
            "runs":runs,
        }

    # Global lessons from repeated blocks.
    ms=[r["market"] for r in source_best]
    market_exp=[num(x,"expectancyR") for x in ms if num(x,"expectancyR") is not None]
    market_wr=[num(x,"winRateResolved") for x in ms if num(x,"winRateResolved") is not None]
    ls=[r.get("limit") for r in source_best if isinstance(r.get("limit"),dict)]
    limit_exp=[num(x,"expectancyR") for x in ls if num(x,"expectancyR") is not None]
    limit_wr=[num(x,"winRateResolved") for x in ls if num(x,"winRateResolved") is not None]
    grades=defaultdict(list)
    for s,d in pair_meta.items(): grades[d["grade"]].append(s)
    ranked=sorted(pair_meta.items(),key=lambda kv:kv[1]["robustScore"],reverse=True)

    recommendations={
      "keepIndicators":["EMA20/50","RSI14","ATR14","ADX14","cross-currency strength"],
      "doNotAddIndicators":True,
      "marketDefault":True,
      "limitDefault":False,
      "executionRule":"MARKET is default for fresh impulse/continuation. LIMIT is conditional only when a real pullback/value structure exists; historical forced LIMIT did not generalize.",
      "biasRule":"Do not average short impulse and long regime blindly. Use horizon evidence as context, but F6 dual-horizon hard classification is rejected because it underperformed F5 on its blind block.",
      "pairAdaptation":"Use conservative pair/archetype adaptation only when the same behavior repeats across multiple independent result blocks; otherwise keep shared core.",
      "riskRule":"SL stays structural+ATR. TP must be economic/liquidity based; reject tiny TP used merely to inflate WR.",
      "offlineNext":"Use this meta file to redesign weights/archetypes, then replay only existing committed result blocks first. Do not call Twelve Data until an offline candidate beats current baselines across multiple old blocks without cherry-picking."
    }

    out={
      "version":"FOREX META V1 OFFLINE - zero provider credits",
      "filesRead":[x["file"] for x in sources],
      "providerCreditsUsed":0,
      "sourceCanonicalTables":sources,
      "sourceForcedComparison":source_best,
      "aggregate":{
        "marketMeanWR":None if not market_wr else round(statistics.mean(market_wr),2),
        "marketMeanExpectancyR":None if not market_exp else round(statistics.mean(market_exp),3),
        "limitMeanWR":None if not limit_wr else round(statistics.mean(limit_wr),2),
        "limitMeanExpectancyR":None if not limit_exp else round(statistics.mean(limit_exp),3),
      },
      "pairGrades":{k:sorted(v) for k,v in grades.items()},
      "pairRanking":[{"symbol":s,**{k:v for k,v in d.items() if k!="runs"}} for s,d in ranked],
      "pairDetail":pair_meta,
      "recommendations":recommendations,
    }
    os.makedirs("data",exist_ok=True)
    with open("data/offline_forex_meta_v1.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({"aggregate":out["aggregate"],"pairGrades":out["pairGrades"],"top":out["pairRanking"][:8],"bottom":out["pairRanking"][-8:]},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
