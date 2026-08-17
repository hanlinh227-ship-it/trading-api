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
VAL=["2026-05-11T08:00:00Z","2026-05-12T08:00:00Z","2026-05-13T08:00:00Z","2026-05-14T08:00:00Z","2026-05-15T08:00:00Z"]
END_DATE="2026-05-16 08:00:00";OUTPUTSIZE=5000;TRADE_EXPIRY_H=30;LIMIT_EXPIRY_H=5
BASE_MODEL={
"EURUSD":"BALANCED","GBPUSD":"BALANCED","USDJPY":"BALANCED","USDCHF":"BALANCED","USDCAD":"REGIME","AUDUSD":"BALANCED","NZDUSD":"BALANCED",
"EURJPY":"BALANCED","EURGBP":"BALANCED","EURCHF":"BALANCED","EURAUD":"REGIME","EURNZD":"BALANCED","EURCAD":"BALANCED","GBPJPY":"BALANCED",
"GBPCHF":"BALANCED","GBPAUD":"BALANCED","GBPNZD":"BALANCED","GBPCAD":"BALANCED","AUDJPY":"REGIME","AUDNZD":"BALANCED","AUDCAD":"BALANCED",
"AUDCHF":"BALANCED","NZDJPY":"BALANCED","NZDCAD":"BALANCED","NZDCHF":"BALANCED","CADJPY":"BALANCED","CADCHF":"BALANCED","CHFJPY":"REGIME"}
RISK_FLOOR={"USD":1.00,"EUR":1.00,"GBP":1.10,"JPY":1.05,"CHF":1.05,"CAD":1.05,"AUD":1.10,"NZD":1.10}
_ST={};_FT={}

def dt(s):return datetime.fromisoformat(s.replace("Z","+00:00"))
def ema(v,n):
    if not v:return None
    a=2/(n+1);x=v[0]
    for z in v[1:]:x=a*z+(1-a)*x
    return x
def rsi(v,n=14):
    if len(v)<n+1:return None
    ds=[b-a for a,b in zip(v[-n-1:-1],v[-n:])];g=sum(max(x,0) for x in ds)/n;l=sum(max(-x,0) for x in ds)/n
    return 100 if l==0 else 100-100/(1+g/l)
def atr(r,n=14):
    if len(r)<n+1:return None
    x=r[-n-1:];tr=[]
    for i in range(1,len(x)):
        p=x[i-1]["close"];q=x[i];tr.append(max(q["high"]-q["low"],abs(q["high"]-p),abs(q["low"]-p)))
    return sum(tr)/len(tr)
def adx(rows,n=14):
    if len(rows)<2*n+2:return None
    trs=[];pdm=[];mdm=[]
    for i in range(1,len(rows)):
        c,p=rows[i],rows[i-1];up=c["high"]-p["high"];dn=p["low"]-c["low"]
        pdm.append(up if up>dn and up>0 else 0);mdm.append(dn if dn>up and dn>0 else 0);trs.append(max(c["high"]-c["low"],abs(c["high"]-p["close"]),abs(c["low"]-p["close"])))
    dx=[]
    for j in range(len(trs)-n+1):
        t=sum(trs[j:j+n])
        if t<=1e-12:continue
        pi=100*sum(pdm[j:j+n])/t;mi=100*sum(mdm[j:j+n])/t;den=pi+mi;dx.append(0 if den<=1e-12 else 100*abs(pi-mi)/den)
    return statistics.mean(dx[-n:]) if len(dx)>=n else (statistics.mean(dx) if dx else None)
def bucket(t,h):return t.replace(hour=(t.hour//h)*h,minute=0,second=0,microsecond=0)
def agg(rows,h):
    d=defaultdict(list);exp=h*4
    for r in rows:d[bucket(r["dt"],h)].append(r)
    out=[]
    for t in sorted(d):
        g=d[t]
        if len(g)<max(1,exp-1):continue
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
    m=statistics.mean(d.values());s=statistics.pstdev(d.values());return {k:(v-m)/s if s>1e-12 else 0 for k,v in d.items()}
def parse_batch(p):
    out={}
    if isinstance(p,dict) and "values" not in p:
        for k,v in p.items():
            if not isinstance(v,dict):continue
            q=v.get("data") if isinstance(v.get("data"),dict) else v
            if isinstance(q,dict) and q.get("values"):out[((q.get("meta") or {}).get("symbol") or k).replace("/","").upper()]=q
    return out
def fetch():
    key=os.environ.get("TWELVEDATA_API_KEY","").strip()
    if not key:raise RuntimeError("TWELVEDATA_API_KEY missing")
    out={};groups=[PAIRS[i:i+7] for i in range(0,28,7)]
    for i,g in enumerate(groups):
        syms=",".join(f"{p[:3]}/{p[3:]}" for p in g);qs=urllib.parse.urlencode({"symbol":syms,"interval":"15min","outputsize":OUTPUTSIZE,"end_date":END_DATE,"timezone":"UTC","order":"asc","apikey":key})
        req=urllib.request.Request("https://api.twelvedata.com/time_series?"+qs,headers={"User-Agent":"trading-api-forex-f6/1.0"})
        with urllib.request.urlopen(req,timeout=100) as z:payload=json.loads(z.read().decode())
        got=parse_batch(payload);miss=[x for x in g if x not in got]
        if miss:raise RuntimeError(f"batch {i+1} missing {miss}: {str(payload)[:2000]}")
        out.update(got);print(f"Fetched {i+1}/4: {','.join(g)}")
        if i<3:time.sleep(66)
    return out
def norm(x):
    o=[]
    for r in x["values"]:
        o.append({"dt":datetime.fromisoformat(r["datetime"]).replace(tzinfo=timezone.utc),"open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"])})
    return sorted(o,key=lambda x:x["dt"])
def strength(frames,cut):
    k=cut.isoformat()
    if k in _ST:return _ST[k]
    hs=(6,24,72);raw={h:{} for h in hs}
    for p,rows in frames.items():
        pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
        if not pre:continue
        now=pre[-1]["close"]
        for h in hs:
            old=before(pre,cut-timedelta(hours=h))
            if old and old>0:raw[h][p]=math.log(now/old)
    zz={h:zmap(raw[h]) for h in hs};tmp={h:{c:[] for c in CCY} for h in hs}
    for h in hs:
        for p,v in zz[h].items():
            b,q=p[:3],p[3:];tmp[h][b].append(v);tmp[h][q].append(-v)
    res={h:{c:(statistics.mean(v) if v else 0) for c,v in tmp[h].items()} for h in hs};_ST[k]=res;return res
def corr(a,b):
    ma=statistics.mean(a);mb=statistics.mean(b);da=[x-ma for x in a];db=[x-mb for x in b];den=math.sqrt(sum(x*x for x in da)*sum(x*x for x in db));return sum(x*y for x,y in zip(da,db))/den if den>1e-12 else 0
def rotation_state(st):
    s6=[st[6][c] for c in CCY];sl=[.60*st[24][c]+.40*st[72][c] for c in CCY];rho=corr(s6,sl);shift=statistics.mean(abs(a-b) for a,b in zip(s6,sl));return {"corr6Long":rho,"meanShift":shift,"active":rho<=-.20 and shift>=.45}
def daily_range(pre):
    vals=[];n=96;x=pre[-n*10:]
    for i in range(0,len(x)-n+1,n):
        g=x[i:i+n]
        if len(g)==n:vals.append(max(r["high"] for r in g)-min(r["low"] for r in g))
    return statistics.median(vals) if vals else None
def feat(pair,rows,cut,st):
    k=(pair,cut.isoformat())
    if k in _FT:return _FT[k]
    pre=[r for r in rows if r["dt"]+timedelta(minutes=15)<=cut]
    if len(pre)<650:return None
    h1=agg(pre,1);h4=agg(pre,4)
    if len(h1)<100 or len(h4)<55:return None
    c=pre[-1]["close"];a15=atr(pre);a1=atr(h1);ax=adx(h1)
    if not a15 or not a1 or ax is None:return None
    mc=[r["close"] for r in pre];h1c=[r["close"] for r in h1];h4c=[r["close"] for r in h4]
    e15=ema(mc[-120:],20);e1=ema(h1c[-120:],20);e1f=ema(h1c[-180:],50);e1p=ema(h1c[-123:-3],20);e4=ema(h4c[-80:],20);e4f=ema(h4c[-120:],50);e4p=ema(h4c[-83:-3],20);rs=rsi(h1c)
    if None in (e15,e1,e1f,e1p,e4,e4f,e4p,rs):return None
    b,q=pair[:3],pair[3:];d6=st[6][b]-st[6][q];d24=st[24][b]-st[24][q];d72=st[72][b]-st[72][q];h4t=1 if c>e4>e4f else -1 if c<e4<e4f else 0;h1t=1 if c>e1>e1f else -1 if c<e1<e1f else 0;h4s=1 if e4>e4p else -1;h1s=1 if e1>e1p else -1;mdev=(c-e15)/a15;mom1=(c-mc[-5])/a15;mom4=(c-mc[-17])/a15
    bal=1.15*d6+.85*d24+.45*d72+1.15*h4t+.45*h4s+1.0*h1t+.40*h1s+.30*max(-1.5,min(1.5,mom1))
    if ax>=24:reg=1.2*d6+.85*d24+.4*d72+1.35*h4t+1.15*h1t+.35*h1s+.30*max(-1.5,min(1.5,mom1))
    elif ax<=17:reg=.25*d6+.60*d24+.45*d72+.55*h4t+.45*h1t-.70*max(-1.5,min(1.5,mdev))
    else:reg=.80*d6+.80*d24+.45*d72+1.0*h4t+.90*h1t+.30*h1s
    longh=.35*d6+1.10*d24+.80*d72+1.30*h4t+.50*h4s+1.10*h1t+.45*h1s+.15*max(-1.5,min(1.5,mom4))
    rot=2.10*d6+.30*d24+.15*d72+.20*h4t+.55*h1t+.35*h1s+.45*max(-1.5,min(1.5,mom1))
    res={"symbol":pair,"entry":c,"atr15":a15,"adr":daily_range(pre) or 6*a1,"ema15":e15,"d6":d6,"d24":d24,"d72":d72,"h4trend":h4t,"h1trend":h1t,"scores":{"BALANCED":bal,"REGIME":reg,"LONGHORIZON":longh,"ROTATION":rot},"riskFloorATR":max(RISK_FLOOR[b],RISK_FLOOR[q]),"pre":pre};_FT[k]=res;return res
def base_side(f):return "BUY" if f["scores"][BASE_MODEL[f["symbol"]]]>=0 else "SELL"
def f6_side(f,rotstate):
    base=base_side(f);longmix=.60*f["d24"]+.40*f["d72"];pairturn=(f["d6"]*longmix<0 and abs(f["d6"])>=.25)
    if rotstate["active"] and pairturn:return "BUY" if f["scores"]["ROTATION"]>=0 else "SELL"
    return base
def barriers(f,side):
    pre=f["pre"];en=f["entry"];a=f["atr15"];adr=f["adr"];sgn=1 if side=="BUY" else -1;vals=(f["d6"],f["d24"],f["d72"],f["h4trend"],f["h1trend"]);aligned=sum(x*sgn>0 for x in vals);recent=pre[-(32 if aligned>=4 else 20):];swing=min(r["low"] for r in recent) if side=="BUY" else max(r["high"] for r in recent);raw=(en-swing+.12*a) if side=="BUY" else (swing-en+.12*a);risk=min(max(raw,f["riskFloorATR"]*a),max(2.8*a,.36*adr));sl=en-risk if side=="BUY" else en+risk;p24=pre[-96:];p72=pre[-288:];e24=max(r["high"] for r in p24) if side=="BUY" else min(r["low"] for r in p24);e72=max(r["high"] for r in p72) if side=="BUY" else min(r["low"] for r in p72);dist=lambda x:(x-en)*sgn;ds=sorted(dist(x) for x in (e24,e72) if dist(x)>.75*a);minecon=max(.90*a,.90*risk);maxmove=max(1.20*a,.80*adr);viable=[d for d in ds if d>=minecon];td=viable[0] if viable else max(minecon,maxmove);td=maxmove if td>1.30*maxmove else td;return sl,en+sgn*td,risk,td/risk
def limit_price(f,side,risk):
    en=f["entry"];e=f["ema15"];a=f["atr15"];sgn=1 if side=="BUY" else -1;fav=e<en if side=="BUY" else e>en;pull=abs(en-e) if fav else .18*risk;pull=min(max(pull,.12*risk),.45*a);return en-sgn*pull
def market(f,rows,cut,side):
    sl,tp,risk,rr=barriers(f,side);fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)]
    for i,r in enumerate(fut,1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl;b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:res="AMBIGUOUS"
        elif a:res="SL"
        elif b:res="TP"
        else:continue
        return {"result":res,"side":side,"bars":i,"entry":f["entry"],"sl":sl,"tp":tp,"plannedRR":rr}
    return {"result":"TIMEOUT","side":side,"bars":len(fut),"entry":f["entry"],"sl":sl,"tp":tp,"plannedRR":rr}
def limit(f,rows,cut,side):
    sl,tp,risk,rr=barriers(f,side);lim=limit_price(f,side,risk);fut=[r for r in rows if cut<=r["dt"]<cut+timedelta(hours=TRADE_EXPIRY_H)];fi=None
    for i,r in enumerate(fut):
        if r["dt"]>=cut+timedelta(hours=LIMIT_EXPIRY_H):break
        tgt=r["high"]>=tp if side=="BUY" else r["low"]<=tp;fill=r["low"]<=lim if side=="BUY" else r["high"]>=lim
        if tgt and not fill:return {"result":"TARGET_BEFORE_FILL","filled":False,"side":side}
        if fill:fi=i;break
    if fi is None:return {"result":"NO_FILL","filled":False,"side":side}
    lr=abs(lim-sl);eff=abs(tp-lim)/lr if lr else None
    for j,r in enumerate(fut[fi:],1):
        a=r["low"]<=sl if side=="BUY" else r["high"]>=sl;b=r["high"]>=tp if side=="BUY" else r["low"]<=tp
        if a and b:res="AMBIGUOUS"
        elif a:res="SL"
        elif b:res="TP"
        else:continue
        return {"result":res,"filled":True,"side":side,"bars":j,"effectiveRR":eff}
    return {"result":"TIMEOUT","filled":True,"side":side,"bars":len(fut)-fi,"effectiveRR":eff}
def hd(f,rows,cut,side,h):
    e=before(rows,cut+timedelta(hours=h))
    if e is None:return None
    mv=e-f["entry"] if side=="BUY" else f["entry"]-e;return {"correct":mv>0,"moveATR":mv/f["atr15"]}
def sm(items):
    r=[x for x in items if x["outcome"]["result"] in ("TP","SL")];w=sum(x["outcome"]["result"]=="TP" for x in r);rr=[x["outcome"]["plannedRR"] for x in r];p=[x["outcome"]["plannedRR"] if x["outcome"]["result"]=="TP" else -1 for x in r];return {"signals":len(items),"resolved":len(r),"wins":w,"losses":len(r)-w,"timeouts":sum(x["outcome"]["result"]=="TIMEOUT" for x in items),"ambiguous":sum(x["outcome"]["result"]=="AMBIGUOUS" for x in items),"winRateResolved":round(100*w/len(r),2) if r else None,"avgPlannedRR":round(statistics.mean(rr),3) if rr else None,"medianPlannedRR":round(statistics.median(rr),3) if rr else None,"expectancyR":round(statistics.mean(p),3) if p else None}
def slm(items):
    fills=[x for x in items if x["outcome"].get("filled")];r=[x for x in fills if x["outcome"]["result"] in ("TP","SL")];w=sum(x["outcome"]["result"]=="TP" for x in r);rr=[x["outcome"]["effectiveRR"] for x in r if x["outcome"].get("effectiveRR") is not None];p=[x["outcome"].get("effectiveRR",0) if x["outcome"]["result"]=="TP" else -1 for x in r];return {"signals":len(items),"fills":len(fills),"fillRate":round(100*len(fills)/len(items),2) if items else None,"resolved":len(r),"wins":w,"losses":len(r)-w,"noFill":sum(x["outcome"]["result"]=="NO_FILL" for x in items),"targetBeforeFill":sum(x["outcome"]["result"]=="TARGET_BEFORE_FILL" for x in items),"winRateResolved":round(100*w/len(r),2) if r else None,"avgEffectiveRR":round(statistics.mean(rr),3) if rr else None,"expectancyR":round(statistics.mean(p),3) if p else None}
def sd(items,key):
    v=[x[key] for x in items if x.get(key)];c=sum(x["correct"] for x in v);return {"tests":len(v),"correct":c,"accuracy":round(100*c/len(v),2) if v else None,"avgMoveATR":round(statistics.mean(x["moveATR"] for x in v),3) if v else None}
def path(items):
    sl=[x for x in items if x["outcome"]["result"]=="SL"];right=sum(x.get("d24") and x["d24"]["correct"] for x in sl);return {"slCount":len(sl),"slButDirection24Correct":right,"slAndDirection24Wrong":len(sl)-right,"pctSLWith24hDirectionCorrect":round(100*right/len(sl),2) if sl else None}
def evaluate(frames,use_f6):
    mk=[];lm=[];byc={};byp={p:[] for p in PAIRS};rot_count=0
    for s in VAL:
        cut=dt(s);st=strength(frames,cut);rs=rotation_state(st);cm=[];cl=[];used=0
        for p in PAIRS:
            f=feat(p,frames[p],cut,st)
            if not f:continue
            bs=base_side(f);side=f6_side(f,rs) if use_f6 else bs
            if use_f6 and side!=bs:used+=1;rot_count+=1
            om=market(f,frames[p],cut,side);ol=limit(f,frames[p],cut,side);rec={"symbol":p,"cutoff":s,"outcome":om,"d6":hd(f,frames[p],cut,side,6),"d12":hd(f,frames[p],cut,side,12),"d24":hd(f,frames[p],cut,side,24)};mk.append(rec);cm.append(rec);li={"symbol":p,"cutoff":s,"outcome":ol};lm.append(li);cl.append(li);byp[p].append(rec)
        byc[s]={"rotationState":rs,"rotationOverrides":used,"market":sm(cm),"limit":slm(cl),"direction12h":sd(cm,"d12"),"direction24h":sd(cm,"d24"),"path":path(cm)}
    return {"market":sm(mk),"limit":slm(lm),"direction6h":sd(mk,"d6"),"direction12h":sd(mk,"d12"),"direction24h":sd(mk,"d24"),"path":path(mk),"rotationOverrides":rot_count,"byCutoff":byc,"byPair":{p:{"market":sm(v),"dir12":sd(v,"d12"),"dir24":sd(v,"d24"),"path":path(v)} for p,v in byp.items()}}
def main():
    raw=fetch();frames={p:norm(raw[p]) for p in PAIRS};base=evaluate(frames,False);f6=evaluate(frames,True)
    result={"generatedAt":datetime.now(timezone.utc).isoformat(),"version":"FOREX F6 cross-currency rotation blind comparator","integrity":{"validationCutoffsRepoSearchedAbsentBeforeCreation":True,"rulesFrozenBeforeReveal":True,"allValidPairsForcedBuyOrSell":True,"sameBlindDataForBaselineAndF6":True,"noTop3":True},"method":{"hypothesis":"F5 collapse may reflect broad FX factor rotation: when the 6h currency-strength vector is negatively correlated with the 24h/72h vector and the cross-sectional shift is material, short-horizon acceleration may deserve temporary priority for pairs whose own 6h strength opposes the long-horizon mix.","rotationGate":{"corr6LongMax":-0.20,"meanShiftMin":0.45,"pairTurnMinAbsD6":0.25},"unchangedFromF5":["EMA20/50, RSI14, ATR14, ADX14 roles","F5 pair baseline models","structural/dynamic SL","economic liquidity/ADR TP","adaptive LIMIT geometry"]},"dataPlan":{"provider":"Twelve Data","interval":"15min","pairs":28,"creditsExpected":28,"validationDates":VAL,"rawCommitted":False},"baselineF5OnSameHoldout":base,"f6RotationOnSameHoldout":f6}
    os.makedirs("data",exist_ok=True)
    with open("data/blind_backtest_forex_f6.json","w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({"baseline":{"market":base["market"],"limit":base["limit"],"dir12":base["direction12h"],"dir24":base["direction24h"],"path":base["path"]},"f6":{"market":f6["market"],"limit":f6["limit"],"dir12":f6["direction12h"],"dir24":f6["direction24h"],"path":f6["path"],"rotationOverrides":f6["rotationOverrides"]},"cutoffs":f6["byCutoff"]},indent=2))
if __name__=="__main__":main()
