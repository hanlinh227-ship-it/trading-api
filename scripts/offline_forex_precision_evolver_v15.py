#!/usr/bin/env python3
import json, math, random, statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier

SNAP="data/provider_snapshots/forex_h1_feb_jul_2026.json"
OUT="data/offline_forex_precision_v15.json"
PAIRS=[
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"]
CCY=["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]
MONTHS=[("MAY","2026-05-01","2026-05-31"),("JUNE","2026-06-01","2026-06-30"),("JULY","2026-07-01","2026-07-31")]


def dt(s): return datetime.fromisoformat(s.replace("Z","+00:00")).replace(tzinfo=timezone.utc) if "+" not in s and not s.endswith("Z") else datetime.fromisoformat(s.replace("Z","+00:00"))
def day(t): return t.date().isoformat()
def sg(x): return 1 if x>0 else -1 if x<0 else 0

def ema(vals,n):
    out=[None]*len(vals)
    if len(vals)<n:return out
    e=sum(vals[:n])/n;out[n-1]=e;k=2/(n+1)
    for i in range(n,len(vals)):e=vals[i]*k+e*(1-k);out[i]=e
    return out

def enrich(raw):
    rows=[{"dt":dt(x[0]),"open":x[1],"high":x[2],"low":x[3],"close":x[4]} for x in raw]
    c=[x["close"] for x in rows];e20=ema(c,20);e50=ema(c,50);tr=[0.0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows);adx=[None]*len(rows)
    plus=[0.0]*len(rows);minus=[0.0]*len(rows)
    for i in range(1,len(rows)):
        tr[i]=max(rows[i]["high"]-rows[i]["low"],abs(rows[i]["high"]-c[i-1]),abs(rows[i]["low"]-c[i-1]))
        up=rows[i]["high"]-rows[i-1]["high"];dn=rows[i-1]["low"]-rows[i]["low"]
        plus[i]=up if up>dn and up>0 else 0;minus[i]=dn if dn>up and dn>0 else 0
    if len(rows)>15:
        a=sum(tr[1:15])/14;pg=sum(plus[1:15])/14;mg=sum(minus[1:15])/14
        ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14;dx=[]
        for i in range(14,len(rows)):
            if i>14:
                a=(a*13+tr[i])/14;pg=(pg*13+plus[i])/14;mg=(mg*13+minus[i])/14
                d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
            atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al)
            pdi=100*pg/a if a else 0;mdi=100*mg/a if a else 0;den=pdi+mdi;dxv=100*abs(pdi-mdi)/den if den else 0;dx.append(dxv)
            if len(dx)>=14:adx[i]=sum(dx[-14:])/14
    # H4 state mapped back to H1 without using incomplete future H4 candles.
    h4=[];bucket=defaultdict(list)
    for i,r in enumerate(rows):bucket[r["dt"].replace(hour=(r["dt"].hour//4)*4,minute=0,second=0,microsecond=0)].append((i,r))
    for t in sorted(bucket):
        z=bucket[t]
        if len(z)==4:h4.append({"t":t,"last_i":z[-1][0],"close":z[-1][1]["close"]})
    hc=[x["close"] for x in h4];h20=ema(hc,20);h50=ema(hc,50);hmap={}
    for j,x in enumerate(h4):
        if h20[j] is not None and h50[j] is not None:
            state=1 if x["close"]>h20[j]>h50[j] else -1 if x["close"]<h20[j]<h50[j] else (1 if x["close"]>h20[j] else -1)
            hmap[x["last_i"]]=(state,h20[j],h50[j])
    last_h4=(0,None,None)
    for i,r in enumerate(rows):
        if i in hmap:last_h4=hmap[i]
        r.update({"ema20":e20[i],"ema50":e50[i],"atr":atr[i],"rsi":rsi[i],"adx":adx[i],"h4":last_h4[0]})
        if i>=72 and atr[i]:
            for h in (3,6,12,24,72):r[f"ret{h}"]=math.log(c[i]/c[i-h]) if c[i-h]>0 else 0
            r["mom6atr"]=(c[i]-c[i-6])/atr[i];r["emaDistAtr"]=(c[i]-e20[i])/atr[i] if e20[i] else 0
            r["session8"]=(c[i]-c[i-8])/atr[i]
    return rows

def make_maps(data):
    # exact timestamp -> symbol,row,index
    maps={s:{r["dt"]:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}
    common=set.intersection(*(set(x) for x in maps.values()))
    times=sorted(t for t in common if t.hour in (0,4,8,12,16,20) and datetime(2026,2,10,tzinfo=timezone.utc)<=t<datetime(2026,8,1,tzinfo=timezone.utc))
    return maps,times

def factor_pack(maps,t):
    out={};disps={}
    for h in (3,6,12,24,72):
        vals={c:[] for c in CCY};pairret={}
        for p in PAIRS:
            i,r=maps[p][t];v=r.get(f"ret{h}")
            if v is None:continue
            pairret[p]=v
        if len(pairret)<24:return None
        mu=statistics.mean(pairret.values());sd=statistics.pstdev(pairret.values()) or 1
        for p,v in pairret.items():
            z=(v-mu)/sd;b,q=p[:3],p[3:];vals[b].append(z);vals[q].append(-z)
        strength={c:(statistics.mean(vals[c]) if vals[c] else 0) for c in CCY}
        coh={c:(abs(sum(sg(x) for x in vals[c]))/len(vals[c]) if vals[c] else 0) for c in CCY}
        order=sorted(CCY,key=lambda c:strength[c],reverse=True);rank={c:i for i,c in enumerate(order)}
        out[h]={"s":strength,"c":coh,"r":rank};disps[h]=statistics.pstdev(strength.values()) or 1
    return out,disps

def candidate_features(pair,row,fp,side):
    b,q=pair[:3],pair[3:];packs,disp=fp
    gaps={h:packs[h]["s"][b]-packs[h]["s"][q] for h in (3,6,12,24,72)}
    coh3=min(packs[3]["c"][b],packs[3]["c"][q]);coh24=min(packs[24]["c"][b],packs[24]["c"][q])
    rank3=packs[3]["r"][q]-packs[3]["r"][b];rank24=packs[24]["r"][q]-packs[24]["r"][b]
    h1=1 if row["close"]>row["ema20"]>row["ema50"] else -1 if row["close"]<row["ema20"]<row["ema50"] else (1 if row["close"]>row["ema20"] else -1)
    ar=row["rsi"] if side==1 else 100-row["rsi"]
    signed=[side*gaps[h] for h in (3,6,12,24,72)]
    grp=0 if "USD" in (b,q) else 1 if "JPY" in (b,q) else 2 if b in ("AUD","NZD","CAD") and q in ("AUD","NZD","CAD") else 3 if b in ("EUR","GBP","CHF") and q in ("EUR","GBP","CHF") else 4
    f=[
        *signed,
        coh3,coh24,side*rank3/7,side*rank24/7,
        side*h1,side*row["h4"],row["adx"]/50,ar/100,
        side*row["mom6atr"]/3,side*row["emaDistAtr"]/3,side*row["session8"]/3,
        abs(gaps[3])/(disp[3]+1e-9),abs(gaps[24])/(disp[24]+1e-9),
        row["dt"].hour/23,grp/4,
    ]
    # Base/quote one-hot gives pair-specific behavior without static winner labels.
    f += [1.0 if b==c else 0.0 for c in CCY]+[1.0 if q==c else 0.0 for c in CCY]
    return f,{"g3":gaps[3],"g6":gaps[6],"g12":gaps[12],"g24":gaps[24],"g72":gaps[72],"coh3":coh3,"coh24":coh24,"rank3":rank3,"rank24":rank24,"h1":h1,"h4":row["h4"],"adx":row["adx"],"rsi":row["rsi"],"mom":row["mom6atr"],"dev":row["emaDistAtr"],"sess":row["session8"]}

def execute(rows,i,side,cfg):
    mode,rr,risk_floor,swing_n,hold,limit_off,expiry,cut_after,cut_r=cfg
    sig=rows[i];atr=sig["atr"]
    if not atr or i+1>=len(rows):return None
    if mode=="MARKET": entry_i=i+1;entry=rows[entry_i]["open"]
    else:
        entry=sig["close"]-side*limit_off*atr;entry_i=None
        for j in range(i+1,min(len(rows),i+1+expiry)):
            if rows[j]["low"]<=entry<=rows[j]["high"]:entry_i=j;break
        if entry_i is None:return None
    recent=rows[max(0,i-swing_n+1):i+1]
    swing=min(x["low"] for x in recent) if side==1 else max(x["high"] for x in recent)
    struct=(entry-swing) if side==1 else (swing-entry);risk=max(risk_floor*atr,struct+.08*atr)
    if risk<=0 or risk>2.8*atr:return None
    sl=entry-side*risk;tp=entry+side*rr*risk
    maxj=min(len(rows),entry_i+hold)
    for j in range(entry_i,maxj):
        b=rows[j]
        hit_sl=(b["low"]<=sl) if side==1 else (b["high"]>=sl)
        hit_tp=(b["high"]>=tp) if side==1 else (b["low"]<=tp)
        if hit_sl and hit_tp:return {"result":"SL","r":-1.0,"bars":j-entry_i+1,"ambiguous":True}
        if hit_sl:return {"result":"SL","r":-1.0,"bars":j-entry_i+1}
        if hit_tp:return {"result":"TP","r":rr,"bars":j-entry_i+1}
        age=j-entry_i+1
        if cut_after and age>=cut_after and b.get("ema20") is not None:
            cur=(b["close"]-entry)/risk*side
            thesis_break=(b["close"]-b["ema20"])*side<0
            if thesis_break and cur<=cut_r:
                return {"result":"CUT","r":max(-1.0,cur),"bars":age,"cutReason":"EMA20_THESIS_BREAK"}
    last=rows[max(entry_i,min(len(rows)-1,maxj-1))]["close"];cur=(last-entry)/risk*side
    return {"result":"CUT","r":max(-1,min(rr,cur)),"bars":maxj-entry_i,"cutReason":"TIMEOUT"}

def build_events(data,maps,times,cfg):
    out=[];scans=0
    fpcache={}
    for t in times:
        fp=factor_pack(maps,t)
        if not fp:continue
        fpcache[t]=fp
        for p in PAIRS:
            i,row=maps[p][t]
            if row.get("adx") is None or row.get("rsi") is None or row.get("ema50") is None:continue
            scans+=1
            # Both side hypotheses are observable; meta-label decides TAKE/NO_TRADE and direction.
            for side in (1,-1):
                feat,meta=candidate_features(p,row,fp,side);o=execute(data[p],i,side,cfg)
                if not o:continue
                out.append({"symbol":p,"time":t,"day":day(t),"x":feat,"side":side,"meta":meta,**o})
    return out,scans

def train_model(train,kind,depth,leaf):
    q=[x for x in train if x["result"] in ("TP","SL")]
    X=np.asarray([x["x"] for x in q],float);y=np.asarray([1 if x["result"]=="TP" else 0 for x in q],int)
    if len(y)<100 or len(set(y))<2:return None
    if kind=="ET":
        model=ExtraTreesClassifier(n_estimators=220,max_depth=depth,min_samples_leaf=leaf,max_features=.7,class_weight="balanced_subsample",n_jobs=-1,random_state=260817)
    else:
        model=HistGradientBoostingClassifier(max_iter=160,max_leaf_nodes=(2**depth-1),min_samples_leaf=leaf,learning_rate=.055,l2_regularization=3.0,random_state=260817)
    model.fit(X,y);return model

def select_month(events,train_end,a,b,kind,depth,leaf,threshold,margin,topk):
    train=[x for x in events if x["day"]<=train_end]
    test=[x for x in events if a<=x["day"]<=b]
    model=train_model(train,kind,depth,leaf)
    if model is None:return []
    X=np.asarray([x["x"] for x in test],float);pr=model.predict_proba(X)[:,1]
    # Avoid taking both BUY/SELL of same pair/time: require winner side to beat the opposite by margin.
    grouped=defaultdict(list)
    for e,p in zip(test,pr):grouped[(e["time"],e["symbol"])].append((float(p),e))
    candidates=[]
    for key,z in grouped.items():
        z=sorted(z,key=lambda v:v[0],reverse=True);best=z[0];other=z[1][0] if len(z)>1 else 0
        if best[0]>=threshold and best[0]-other>=margin:
            q=dict(best[1]);q["prob"]=best[0];q["edge"]=best[0]-other;candidates.append(q)
    byday=defaultdict(list)
    for e in candidates:byday[e["day"]].append(e)
    selected=[]
    for d,z in byday.items():selected.extend(sorted(z,key=lambda x:(x["prob"],x["edge"]),reverse=True)[:topk])
    return selected

def summarize(rows):
    tp=sum(x["result"]=="TP" for x in rows);sl=sum(x["result"]=="SL" for x in rows);cuts=[x for x in rows if x["result"]=="CUT"];den=tp+sl
    return {"n":len(rows),"tp":tp,"sl":sl,"cut":len(cuts),"wr":round(100*tp/den,2) if den else 0,"meanR":round(statistics.mean(x["r"] for x in rows),3) if rows else -9,"avgCutR":round(statistics.mean(x["r"] for x in cuts),3) if cuts else None,"cutRate":round(100*len(cuts)/len(rows),2) if rows else 0,"symbolsTraded":len(set(x["symbol"] for x in rows))}

def walkforward(events,hp):
    kind,depth,leaf,threshold,margin,topk=hp
    folds={};allsel=[]
    specs=[("MAY","2026-04-30","2026-05-01","2026-05-31"),("JUNE","2026-05-31","2026-06-01","2026-06-30"),("JULY","2026-06-30","2026-07-01","2026-07-31")]
    for name,te,a,b in specs:
        z=select_month(events,te,a,b,kind,depth,leaf,threshold,margin,topk);folds[name]=summarize(z);allsel+=z
    folds["COMBINED"]=summarize(allsel);return folds,allsel

def quality(folds):
    c=folds["COMBINED"]
    monthly=[folds[x] for x in ("MAY","JUNE","JULY")]
    enough=c["n"]>=24 and all(x["n"]>=5 for x in monthly)
    target=enough and c["wr"]>=80 and c["meanR"]>0 and c["cutRate"]<=50 and all(x["wr"]>=65 for x in monthly)
    scarcity=sum(max(0,5-x["n"])*5 for x in monthly)+max(0,24-c["n"])*2
    return (1 if target else 0,c["wr"]-scarcity,min(x["wr"] for x in monthly),c["meanR"],-c["cutRate"],c["n"])

def config_space():
    # RR is strictly 1.0 or 1.5. CUT does not change initial planned RR.
    out=[]
    for mode in ("MARKET","LIMIT"):
      offs=(0.0,) if mode=="MARKET" else (.20,.35,.50,.70)
      exps=(1,) if mode=="MARKET" else (2,3,4)
      for rr in (1.0,1.5):
       for rf in (.65,.80,1.0,1.20):
        for sw in (6,12,18):
         for hold in (12,18,24):
          for off in offs:
           for exp in exps:
            for ca in (0,2,3,4):
             crs=(0.0,) if ca==0 else (-.15,-.30,-.45)
             for cr in crs:out.append((mode,rr,rf,sw,hold,off,exp,ca,cr))
    return out

def main():
    doc=json.load(open(SNAP,encoding="utf-8"))
    if doc.get("coverageCount")!=28 or set(doc.get("data",{}))!=set(PAIRS):raise RuntimeError("Snapshot not 28/28")
    data={p:enrich(doc["data"][p]) for p in PAIRS};maps,times=make_maps(data)
    rng=random.Random(15080);cfgs=config_space();rng.shuffle(cfgs)
    # Broad but bounded evolutionary search. Each execution config gets a compact model/threshold search.
    best=None;tested=0;best_payload=None
    hp_space=[]
    for kind in ("ET","HGB"):
      for depth in (3,5,7):
       for leaf in (8,15,25,40):
        for th in (.62,.66,.70,.74,.78,.82,.86,.90,.93):
         for margin in (.00,.04,.08,.12,.16):
          for topk in (1,2):hp_space.append((kind,depth,leaf,th,margin,topk))
    # First 180 execution configurations are enough for iterative V15; next version can expand around winner.
    for ci,cfg in enumerate(cfgs[:180]):
        events,scans=build_events(data,maps,times,cfg)
        if len(events)<200:continue
        # Sample hyperparameters, but preserve high-precision thresholds heavily.
        hps=list(hp_space);rng.shuffle(hps)
        for hp in hps[:55]:
            folds,sel=walkforward(events,hp);q=quality(folds);tested+=1
            if best is None or q>best:
                best=q;best_payload={"execution":{"mode":cfg[0],"rr":cfg[1],"riskFloorATR":cfg[2],"swingHours":cfg[3],"maxHoldH":cfg[4],"limitOffsetATR":cfg[5],"limitExpiryH":cfg[6],"cutAfterH":cfg[7],"cutRThreshold":cfg[8]},"model":{"kind":hp[0],"depth":hp[1],"leaf":hp[2],"threshold":hp[3],"sideMargin":hp[4],"topKPerDay":hp[5]},"folds":folds,"quality":q,"eventCount":len(events),"scanCount":scans}
                print("BEST",tested,json.dumps(best_payload),flush=True)
            if q[0]==1:
                break
        if best and best[0]==1:break
    result={"version":"FOREX_PRECISION_V15","providerCreditsUsed":0,"snapshot":SNAP,"scanUniverse":PAIRS,"scanUniverseCount":28,"allSymbolsScanned":True,"hiddenFinalAugustFetched":False,"testedCandidates":tested,"best":best_payload,"preAugustTargetMet":bool(best and best[0]==1),"promotionRule":"Require combined May-Jul TP/SL WR >=80, planned RR exactly 1.0 or 1.5, positive expectancy including CUT, <=50% CUT rate, >=24 selected trades and >=5/month; final Aug remains untouched."}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(result,open(OUT,"w"),indent=2)
    print("FINAL",json.dumps(result,indent=2),flush=True)

if __name__=="__main__":main()
