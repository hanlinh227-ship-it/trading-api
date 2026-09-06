#!/usr/bin/env python3
"""Bybit MultiCoin StateFlow Dynamic V2 — research only.

V2 changes method after V1 fixed-RR baseline failed. To avoid reusing V1 OOS
results, V2 validates on an older untouched chronological block: 300d DEV +
3x50d OOS ending 500 days before the current dataset end.

Changes: independent LONG/SHORT profiles; trend reclaim, break-retest, range
fade and sweep-reclaim families; native stop + state target + profit lock +
ATR trailing + smart cut + timeout. Closed-bar signals, next-bar entry, no
position overlap, costs included and same-bar stop/target ambiguity => stop.
Historical OHLCV is not treated as L2/taker-flow/liquidation/OI replay.
"""
from __future__ import annotations
import argparse,dataclasses,hashlib,itertools,json,math,time,urllib.parse,urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path

UNIVERSE=["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","SOLUSDT","TRXUSDT","DOGEUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT","BCHUSDT","XLMUSDT","DOTUSDT","NEARUSDT","UNIUSDT","AAVEUSDT","HBARUSDT"]
BASE="https://data-api.binance.vision/api/v3/klines";INTERVAL="15m";INTERVAL_MS=900_000;DAY_MS=86_400_000
HISTORY_DAYS=1100;SEEN_V1_BUFFER_DAYS=500;DEV_DAYS=300;OOS_DAYS=50;OOS_WINDOWS=3
BASE_COST_BPS=13.0;TARGET_WR=.80;WORST_FLOOR=.70;MIN_OOS=60;MIN_WIN=20;MIN_DEV_SIDE=40

@dataclass(frozen=True)
class Bar: ts:int;o:float;h:float;l:float;c:float;v:float
@dataclass(frozen=True)
class Profile:
    family:str;side:int;sep:float;quality:float;vol_min:float;trigger:float
    stop_atr:float;target_atr:float;lock_trigger_atr:float;trail_atr:float;cut_atr:float;hold:int
@dataclass
class Stats:
    trades:int=0;wins:int=0;losses:int=0;timeouts:int=0;net_r:float=0.;gross_r:float=0.;costs_r:float=0.;max_dd_r:float=0.;longs:int=0;shorts:int=0;long_wins:int=0;short_wins:int=0;max_consecutive_losses:int=0
    @property
    def wr(self):return self.wins/self.trades if self.trades else 0.
    @property
    def exp(self):return self.net_r/self.trades if self.trades else 0.

def iso(ts):return datetime.fromtimestamp(ts/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def getj(url,retries=7):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"bybit-stateflow-dynamic-v2/1.0"})
            with urllib.request.urlopen(req,timeout=35) as r:return json.loads(r.read().decode())
        except Exception as e:last=e;time.sleep(min(4,.3*(2**n)))
    raise RuntimeError(last)
def load(sym):
    now=int(time.time()*1000);end=(now//INTERVAL_MS)*INTERVAL_MS-1;start=end-HISTORY_DAYS*DAY_MS;rows=[];cur=start
    while cur<=end:
        q=urllib.parse.urlencode({"symbol":sym,"interval":INTERVAL,"startTime":cur,"endTime":end,"limit":1000});batch=getj(BASE+"?"+q)
        if not batch:break
        rows.extend(batch);nxt=int(batch[-1][0])+INTERVAL_MS
        if nxt<=cur:raise RuntimeError("pagination stalled")
        cur=nxt;time.sleep(.015)
    u={int(x[0]):x for x in rows if start<=int(x[0])<=end};xs=[u[k] for k in sorted(u)];b=[Bar(int(x[0]),float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])) for x in xs]
    if len(b)<40_000:raise RuntimeError(f"insufficient history {len(b)}")
    gaps=[(a.ts,z.ts) for a,z in zip(b,b[1:]) if z.ts-a.ts!=INTERVAL_MS];expected=(b[-1].ts-b[0].ts)//INTERVAL_MS+1
    return b,{"source":"BinanceSpotDataAPI","symbol":sym,"interval":INTERVAL,"first":iso(b[0].ts),"last":iso(b[-1].ts),"bars":len(b),"expected":expected,"coverage":len(b)/expected,"gaps":len(gaps),"gap_examples":[(iso(a),iso(z)) for a,z in gaps[:8]]}
def ema(x,p):
    a=2/(p+1);out=[math.nan]*len(x);v=x[0];out[0]=v
    for i in range(1,len(x)):v=a*x[i]+(1-a)*v;out[i]=v
    return out
def prep(b):
    n=len(b);c=[x.c for x in b];e20=ema(c,20);e60=ema(c,60);tr=[0.]*n
    for i,x in enumerate(b):tr[i]=x.h-x.l if i==0 else max(x.h-x.l,abs(x.h-b[i-1].c),abs(x.l-b[i-1].c))
    atr=ema(tr,14);vs=[math.nan]*n;q=deque();s=0.
    for i,x in enumerate(b):
        q.append(x.v);s+=x.v
        if len(q)>20:s-=q.popleft()
        if len(q)==20:vs[i]=s/20
    hi20=[math.nan]*n;lo20=[math.nan]*n;mean20=[math.nan]*n
    for i in range(20,n):
        z=b[i-20:i];hi20[i]=max(x.h for x in z);lo20[i]=min(x.l for x in z);mean20[i]=sum(x.c for x in z)/20
    eff=[0.]*n
    for i in range(20,n):
        path=sum(abs(c[j]-c[j-1]) for j in range(i-19,i+1));eff[i]=abs(c[i]-c[i-20])/path if path else 0.
    slope=[0.]*n
    for i in range(8,n):slope[i]=(e20[i]-e20[i-8])/max(atr[i],1e-12)
    return {"e20":e20,"e60":e60,"atr":atr,"vs":vs,"hi20":hi20,"lo20":lo20,"mean20":mean20,"eff":eff,"slope":slope}
def sig(i,b,I,p):
    if i<70 or i>=len(b)-2:return False
    x=b[i];prev=b[i-1];a=I["atr"][i]
    if not math.isfinite(a) or a<=0:return False
    e20,e60=I["e20"][i],I["e60"][i];sep=(e20-e60)/a;eff=I["eff"][i];vs=I["vs"][i];vr=x.v/vs if vs and math.isfinite(vs) and vs>0 else 0
    if vr<p.vol_min:return False
    cr=max(x.h-x.l,1e-12);loc=(x.c-x.l)/cr if p.side>0 else (x.h-x.c)/cr;h20,l20=I["hi20"][i],I["lo20"][i];slp=I["slope"][i]
    if p.family=="TREND_RECLAIM":
        if eff<p.quality:return False
        if p.side>0:
            touched=min(z.l for z in b[i-4:i+1])<=e20+p.trigger*a;return sep>=p.sep and slp>0 and touched and x.c>e20 and x.c>x.o and x.c>=prev.c and loc>=.58
        touched=max(z.h for z in b[i-4:i+1])>=e20-p.trigger*a;return sep<=-p.sep and slp<0 and touched and x.c<e20 and x.c<x.o and x.c<=prev.c and loc>=.58
    if p.family=="BREAK_RETEST":
        if eff<p.quality or not math.isfinite(h20):return False
        ph=max(z.h for z in b[i-23:i-3]);pl=min(z.l for z in b[i-23:i-3]);recent=b[i-3:i]
        if p.side>0:
            broke=any(z.h>ph+p.trigger*a and z.c>ph for z in recent);return sep>=p.sep and broke and x.l<=ph+.18*a and x.c>ph and x.c>x.o and loc>=.55
        broke=any(z.l<pl-p.trigger*a and z.c<pl for z in recent);return sep<=-p.sep and broke and x.h>=pl-.18*a and x.c<pl and x.c<x.o and loc>=.55
    if p.family=="RANGE_FADE":
        if eff>p.quality or not math.isfinite(h20):return False
        m=I["mean20"][i]
        if p.side>0:return (m-x.l)/a>=p.trigger and x.c>x.o and x.c>prev.c and loc>=.60
        return (x.h-m)/a>=p.trigger and x.c<x.o and x.c<prev.c and loc>=.60
    if p.family=="SWEEP_RECLAIM":
        if not math.isfinite(h20):return False
        if p.side>0:return x.l<l20-p.trigger*a and x.c>l20 and x.c>x.o and loc>=.60
        return x.h>h20+p.trigger*a and x.c<h20 and x.c<x.o and loc>=.60
    return False
def trade_from(i,b,I,p,cost_bps=BASE_COST_BPS,delay=0,hi=None):
    hi=len(b)-1 if hi is None else hi;ei=i+1+delay
    if ei>=hi:return None
    entry=b[ei].o;a=max(I["atr"][i],1e-12);stopd=p.stop_atr*a
    if stopd/entry<.0015:return None
    side=p.side;hard=entry-side*stopd;target=entry+side*p.target_atr*a;cost_r=(cost_bps/10000)*entry/stopd;lock_trigger=p.lock_trigger_atr*a;trail_dist=p.trail_atr*a;best=entry;dyn_stop=hard;timed=True;gross=None;last=ei
    for j in range(ei,min(hi+1,ei+p.hold+1)):
        x=b[j];last=j;hit_stop=x.l<=dyn_stop if side>0 else x.h>=dyn_stop
        if hit_stop:gross=side*(dyn_stop-entry)/stopd;timed=False;break
        hit_target=x.h>=target if side>0 else x.l<=target
        if hit_target:gross=side*(target-entry)/stopd;timed=False;break
        fav=x.h if side>0 else x.l;best=max(best,fav) if side>0 else min(best,fav);mfe=side*(best-entry)
        if mfe>=lock_trigger:
            cushion=(cost_bps/10000)*entry*1.15;lock=entry+side*cushion
            if side>0:dyn_stop=max(dyn_stop,lock,best-trail_dist)
            else:dyn_stop=min(dyn_stop,lock,best+trail_dist)
        adverse=side*(x.c-entry);e20=I["e20"][j];cut_state=x.c<e20-p.cut_atr*a if side>0 else x.c>e20+p.cut_atr*a;reversal=(x.c<x.o and x.c<b[j-1].c) if side>0 else (x.c>x.o and x.c>b[j-1].c)
        if j>=ei+2 and cut_state and reversal and adverse<0:gross=side*(x.c-entry)/stopd;timed=False;break
    if gross is None:gross=side*(b[last].c-entry)/stopd
    return last,gross,gross-cost_r,cost_r,timed
def run_side(b,I,p,lo,hi,cost_bps=BASE_COST_BPS,delay=0):
    s=Stats();eq=peak=0.;ls=0;i=max(lo,70)
    while i<hi-2:
        if not sig(i,b,I,p):i+=1;continue
        t=trade_from(i,b,I,p,cost_bps,delay,hi)
        if not t:i+=1;continue
        last,g,n,c,timed=t;s.trades+=1;s.gross_r+=g;s.net_r+=n;s.costs_r+=c
        if p.side>0:s.longs+=1
        else:s.shorts+=1
        if timed:s.timeouts+=1
        if n>0:
            s.wins+=1;ls=0
            if p.side>0:s.long_wins+=1
            else:s.short_wins+=1
        else:s.losses+=1;ls+=1;s.max_consecutive_losses=max(s.max_consecutive_losses,ls)
        eq+=n;peak=max(peak,eq);s.max_dd_r=max(s.max_dd_r,peak-eq);i=last+1
    return s
def run_combo(b,I,longp,shortp,lo,hi,cost_bps=BASE_COST_BPS,delay=0):
    s=Stats();eq=peak=0.;ls=0;i=max(lo,70)
    while i<hi-2:
        L=sig(i,b,I,longp);S=sig(i,b,I,shortp)
        if L and S:i+=1;continue
        p=longp if L else shortp if S else None
        if not p:i+=1;continue
        t=trade_from(i,b,I,p,cost_bps,delay,hi)
        if not t:i+=1;continue
        last,g,n,c,timed=t;s.trades+=1;s.gross_r+=g;s.net_r+=n;s.costs_r+=c
        if p.side>0:s.longs+=1
        else:s.shorts+=1
        if timed:s.timeouts+=1
        if n>0:
            s.wins+=1;ls=0
            if p.side>0:s.long_wins+=1
            else:s.short_wins+=1
        else:s.losses+=1;ls+=1;s.max_consecutive_losses=max(s.max_consecutive_losses,ls)
        eq+=n;peak=max(peak,eq);s.max_dd_r=max(s.max_dd_r,peak-eq);i=last+1
    return s
def merge(xs):
    o=Stats()
    for s in xs:
        for f in ("trades","wins","losses","timeouts","longs","shorts","long_wins","short_wins"):setattr(o,f,getattr(o,f)+getattr(s,f))
        for f in ("net_r","gross_r","costs_r"):setattr(o,f,getattr(o,f)+getattr(s,f))
        o.max_dd_r=max(o.max_dd_r,s.max_dd_r);o.max_consecutive_losses=max(o.max_consecutive_losses,s.max_consecutive_losses)
    return o
MGMT=[(1.6,.55,.28,.35,.30,16),(2.0,.65,.32,.42,.35,20),(2.4,.75,.36,.48,.40,24),(2.0,.85,.40,.50,.42,28)]
def candidates(side):
    for fam in ("TREND_RECLAIM","BREAK_RETEST","RANGE_FADE","SWEEP_RECLAIM"):
        seps=(.08,.18);qs=(.20,.32);vols=(.75,1.05);trigs={"TREND_RECLAIM":(.08,.22),"BREAK_RETEST":(.00,.08),"RANGE_FADE":(.75,1.05),"SWEEP_RECLAIM":(.02,.08)}[fam];mids=(0,1) if fam in ("RANGE_FADE","SWEEP_RECLAIM") else (1,3)
        for sep,q,v,t,midx in itertools.product(seps,qs,vols,trigs,mids):
            st,tp,lock,tr,cut,hold=MGMT[midx];yield Profile(fam,side,sep,q,v,t,st,tp,lock,tr,cut,hold)
def score(s):
    cover=min(1,s.trades/MIN_DEV_SIDE);return (1 if s.trades>=MIN_DEV_SIDE else 0,1 if s.exp>0 else 0,s.wr*cover,s.exp,-s.max_dd_r,s.trades)
def idx(b,st,en):
    lo=next((i for i,x in enumerate(b) if x.ts>=st),None);hi=None
    for i,x in enumerate(b):
        if x.ts<=en:hi=i
        else:break
    return (lo,hi) if lo is not None and hi is not None and hi>lo else None
def clean(b,lo,hi):return all(b[i].ts-b[i-1].ts==INTERVAL_MS for i in range(lo+1,hi+1))
def statd(s):return {"trades":s.trades,"wins":s.wins,"losses":s.losses,"timeouts":s.timeouts,"win_rate":round(s.wr,6),"expectancy_r":round(s.exp,6),"net_r":round(s.net_r,4),"gross_r":round(s.gross_r,4),"costs_r":round(s.costs_r,4),"max_dd_r":round(s.max_dd_r,4),"max_consecutive_losses":s.max_consecutive_losses,"longs":s.longs,"shorts":s.shorts,"long_win_rate":round(s.long_wins/s.longs,6) if s.longs else None,"short_win_rate":round(s.short_wins/s.shorts,6) if s.shorts else None}
def pd(p):return dataclasses.asdict(p)
def ph(p):return hashlib.sha256(json.dumps(pd(p),sort_keys=True,separators=(",",":")).encode()).hexdigest()[:16]
def calibrate(sym,b,manifest):
    I=prep(b);anchor=b[-1].ts-SEEN_V1_BUFFER_DAYS*DAY_MS;oos_end=anchor;oos_start=oos_end-OOS_WINDOWS*OOS_DAYS*DAY_MS+INTERVAL_MS;dev_end=oos_start-INTERVAL_MS;dev_start=dev_end-DEV_DAYS*DAY_MS+INTERVAL_MS;di=idx(b,dev_start,dev_end)
    if not di or not clean(b,*di):return {"symbol":sym,"status":"DATA_GAP","reason":"V2 DEV unavailable/gapped","manifest":manifest}
    windows=[]
    for k in range(OOS_WINDOWS):
        st=oos_start+k*OOS_DAYS*DAY_MS;en=st+OOS_DAYS*DAY_MS-INTERVAL_MS;z=idx(b,st,en)
        if not z or not clean(b,*z):return {"symbol":sym,"status":"DATA_GAP","reason":f"V2 OOS{k+1} unavailable/gapped","manifest":manifest}
        windows.append(z)
    ranked={}
    for side in (1,-1):
        arr=[]
        for p in candidates(side):
            s=run_side(b,I,p,di[0],di[1]);arr.append((score(s),p,s))
        arr.sort(key=lambda z:z[0],reverse=True);ranked[side]=arr
    lp,ld=ranked[1][0][1],ranked[1][0][2];sp,sdv=ranked[-1][0][1],ranked[-1][0][2];ws=[run_combo(b,I,lp,sp,lo,hi) for lo,hi in windows];agg=merge(ws);worst=min(x.wr for x in ws)
    base=agg.wr>=TARGET_WR and worst>=WORST_FLOOR and agg.trades>=MIN_OOS and all(x.trades>=MIN_WIN for x in ws) and agg.exp>0 and all(x.net_r>0 for x in ws)
    st15=merge([run_combo(b,I,lp,sp,lo,hi,cost_bps=BASE_COST_BPS*1.5) for lo,hi in windows]);st20=merge([run_combo(b,I,lp,sp,lo,hi,cost_bps=BASE_COST_BPS*2) for lo,hi in windows]);delay=merge([run_combo(b,I,lp,sp,lo,hi,delay=1) for lo,hi in windows]);robust=st15.exp>0 and st20.exp>0 and delay.exp>0;status="LOCKED" if base and robust else "RESEARCH";reason=[]
    if status!="LOCKED":
        if agg.wr<TARGET_WR:reason.append("OOS_WR_LT_80")
        if worst<WORST_FLOOR:reason.append("WORST_WINDOW_LT_70")
        if agg.trades<MIN_OOS:reason.append("OOS_TRADES_LT_60")
        if any(x.trades<MIN_WIN for x in ws):reason.append("WINDOW_TRADES_LT_20")
        if agg.exp<=0:reason.append("NONPOSITIVE_EXPECTANCY")
        if any(x.net_r<=0 for x in ws):reason.append("NEGATIVE_WINDOW_R")
        if not robust:reason.append("STRESS_FAIL")
    return {"symbol":sym,"status":status,"reason":"PASS" if status=="LOCKED" else reason,"profile_version":"stateflow_dynamic_v2","long_profile_hash":ph(lp),"short_profile_hash":ph(sp),"long_params":pd(lp),"short_params":pd(sp),"manifest":manifest,"validation_block_policy":{"v1_seen_buffer_days":SEEN_V1_BUFFER_DAYS,"dev_days":DEV_DAYS,"oos_windows":OOS_WINDOWS,"oos_days":OOS_DAYS},"dev_range":[iso(b[di[0]].ts),iso(b[di[1]].ts)],"dev_long":statd(ld),"dev_short":statd(sdv),"oos_windows":[{"range":[iso(b[lo].ts),iso(b[hi].ts)],**statd(s)} for (lo,hi),s in zip(windows,ws)],"oos_aggregate":statd(agg),"worst_window_wr":round(worst,6),"stress":{"cost_1_5x":statd(st15),"cost_2_0x":statd(st20),"entry_delay_1bar":statd(delay),"pass":robust},"gate":{"target_wr":TARGET_WR,"worst_window_floor":WORST_FLOOR,"min_oos_trades":MIN_OOS,"min_window_trades":MIN_WIN,"base_pass":base,"locked":status=="LOCKED"},"limitations":["OHLCV state proxy only","V2 validation block is disjoint from V1 evidence","No L2/taker-flow/liquidation/OI replay","Microstructure replay / forward-paper required before production"]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--symbols",default=",".join(UNIVERSE));ap.add_argument("--out",default="research/results/bybit_multicoin_stateflow_dynamic_v2.json");a=ap.parse_args();syms=[x.strip().upper() for x in a.symbols.split(",") if x.strip()];res=[];print("=== BYBIT MULTICOIN STATEFLOW DYNAMIC V2 ===",flush=True)
    for n,sym in enumerate(syms,1):
        print(f"[{n}/{len(syms)}] {sym} load",flush=True)
        try:b,m=load(sym);print(f"DATA {sym} bars={m['bars']} coverage={m['coverage']:.6f} gaps={m['gaps']}",flush=True);r=calibrate(sym,b,m)
        except Exception as e:r={"symbol":sym,"status":"ERROR","reason":repr(e)}
        res.append(r)
        if r.get("oos_aggregate"):
            x=r["oos_aggregate"];print(f"RESULT {sym} {r['status']} WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_window_wr']:.2f}% LONG={r['long_params']['family']} SHORT={r['short_params']['family']} reason={r['reason']}",flush=True)
        else:print("RESULT",sym,r["status"],r.get("reason"),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);summary={"generated_at":datetime.now(timezone.utc).isoformat(),"engine":"BYBIT_MULTICOIN_STATEFLOW_DYNAMIC_V2","research_only":True,"universe":syms,"locked":[r["symbol"] for r in res if r.get("status")=="LOCKED"],"unresolved":[r["symbol"] for r in res if r.get("status")!="LOCKED"],"results":res};out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");print("LOCKED",summary["locked"],flush=True);print("REPORT",out,flush=True)
if __name__=="__main__":main()
