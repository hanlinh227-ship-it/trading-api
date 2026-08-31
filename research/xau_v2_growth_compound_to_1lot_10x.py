#!/usr/bin/env python3
"""XAU V2 — true-compound growth model to 1.00 standard lot.

Research-only. Independent of BTC ladder logic.
Changes from V1 are evidence-driven and not validation-window tuned:
- deduplicate source timestamps before indicators/backtest;
- stronger but still minimal H1 trend regime: EMA20/EMA50 + ATR14 separation;
- M15 EMA20 pullback/reclaim only, liquid-hours entry filter, no oscillator stack;
- lower target RR candidates (1.30-1.60) to avoid V1's sub-breakeven 2R hit rate;
- bar-close break-even protection after >=0.90R progress;
- growth risk is 4% of CURRENT equity, but contracts after SL (anti-martingale).

PASS requires a >=1.00 STANDARD XAU lot trade to actually close at TP.
"""
from __future__ import annotations
import bisect,csv,hashlib,math,statistics
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import List,Optional,Tuple

BASE=20.0; OZ=100.0; STEP=0.0001; MILESTONE=1.0
LEVERAGE=500.0; MARGIN_CAP=0.35; COST_PRICE=0.30
RISK_NORMAL=0.040; RISK_RECOVERY=0.020; RISK_L1=0.025; RISK_L2=0.015; RISK_L3=0.0075
SWING_BARS=4; SWING_BUF=.10; MAX_SL_ATR=1.80
BODY_MIN=.12; BODY_MAX=.62; RANGE_MAX=1.00; PULL_BARS=4
BE_TRIGGER_R=.90; BE_LOCK_R=.05
M15_PATH=Path('research/data/XAUUSD_M15.csv'); H1_PATH=Path('research/data/XAUUSD_H1.csv')

@dataclass(frozen=True)
class Bar:
    t:datetime;o:float;h:float;l:float;c:float;v:float
@dataclass(frozen=True)
class Cfg:
    h1_sep_atr:float; pull_tol:float; max_dist:float; min_sl_atr:float; rr:float
    @property
    def rec_rr(self): return self.rr+.20
@dataclass
class Pos:
    d:int;en:float;sl:float;initial_sl:float;tp:float;lot:float;rec:bool;opened:datetime;be:bool=False
@dataclass
class R:
    status:str;start:datetime;end:datetime;days:float;eq:float;peak:float;min_eq:float;dd:float;maxlot:float
    trades:int;wins:int;losses:int;be_exits:int;rec_trades:int;one_attempts:int;first_one:str;pass_at:str;pass_eq:float
    margin_caps:int;skip_wide:int;skip_chase:int

def ptime(s):
    s=s.strip().replace('T',' ').replace('Z','')
    for f in ('%Y-%m-%d %H:%M:%S','%Y.%m.%d %H:%M','%Y.%m.%d %H:%M:%S','%Y-%m-%d %H:%M'):
        try:return datetime.strptime(s,f).replace(tzinfo=timezone.utc)
        except ValueError:pass
    x=float(s);x=x/1000 if x>1e10 else x
    return datetime.fromtimestamp(x,tz=timezone.utc)

def load(path:Path):
    rows=0; bad=0; d={}
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f); names={x.strip().lower():x for x in rd.fieldnames or []}
        tk=names.get('time') or names.get('datetime') or names.get('timestamp'); vk=names.get('tick_volume') or names.get('volume')
        if not tk or not all(k in names for k in ('open','high','low','close')): raise RuntimeError(rd.fieldnames)
        for row in rd:
            rows+=1
            try:
                t=ptime(row[tk]);o=float(row[names['open']]);h=float(row[names['high']]);l=float(row[names['low']]);c=float(row[names['close']]);v=float(row[vk]) if vk and row.get(vk) else 0.
                if not(o>0 and h>=max(o,c) and l<=min(o,c) and h>=l): raise ValueError
                d[t]=Bar(t,o,h,l,c,v) # deterministic keep-last de-dup
            except Exception:bad+=1
    bars=[d[k] for k in sorted(d)]
    return bars,rows,rows-bad-len(bars),bad

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for x in iter(lambda:f.read(1<<20),b''):h.update(x)
    return h.hexdigest()

def audit(name,b,raw,dups,bad,mins):
    gaps=short=long=0;mg=0
    for a,z in zip(b,b[1:]):
        dt=(z.t-a.t).total_seconds()/60
        if dt>mins:
            gaps+=1;mg=max(mg,dt)
            if dt>=1440:long+=1
            else:short+=1
    print(f'DATA_AUDIT {name} raw={raw} clean={len(b)} duplicateRemoved={dups} badRemoved={bad} range={b[0].t.isoformat()}->{b[-1].t.isoformat()} gapIntervals={gaps} shortGaps={short} longGaps={long} maxGapMin={mg:.1f}',flush=True)

def ema(v,p):
    out=[math.nan]*len(v);a=2/(p+1);x=v[0];out[0]=x
    for i in range(1,len(v)):x=a*v[i]+(1-a)*x;out[i]=x
    return out

def atr(b,p):
    tr=[]
    for i,z in enumerate(b):
        tr.append(z.h-z.l if i==0 else max(z.h-z.l,abs(z.h-b[i-1].c),abs(z.l-b[i-1].c)))
    out=[math.nan]*len(b)
    if len(b)<p:return out
    x=sum(tr[:p])/p;out[p-1]=x
    for i in range(p,len(b)):x=(x*(p-1)+tr[i])/p;out[i]=x
    return out

def volfloor(v):return 0. if v<STEP else math.floor((v+1e-12)/STEP)*STEP

def riskpct(eq,peak,ls):
    if ls>=3:return RISK_L3
    if ls==2:return RISK_L2
    if ls==1:return RISK_L1
    if eq<peak-1e-9:return RISK_RECOVERY
    return RISK_NORMAL

def liquid_time(t):
    # EA remains online all day; this is only a new-entry quality gate.
    # Avoid rollover/very thin hours. Friday late UTC is also avoided.
    if t.weekday()>=5:return False
    if not(6<=t.hour<=20):return False
    if t.weekday()==4 and t.hour>=18:return False
    return True

def sig(i,m,e20,a,h,h20,h50,ha,hend,cfg):
    if i<80 or not liquid_time(m[i].t):return 0
    av=a[i]
    if not math.isfinite(av) or av<=0:return 0
    close_t=m[i].t+timedelta(minutes=15);hi=bisect.bisect_right(hend,close_t)-1
    if hi<60:return 0
    hav=ha[hi]
    if not math.isfinite(hav) or hav<=0:return 0
    sep=(h20[hi]-h50[hi])/hav
    bull=h20[hi]>h50[hi] and sep>=cfg.h1_sep_atr and h[hi].c>h20[hi] and h20[hi]>h20[hi-3] and h50[hi]>=h50[hi-3]
    bear=h20[hi]<h50[hi] and -sep>=cfg.h1_sep_atr and h[hi].c<h20[hi] and h20[hi]<h20[hi-3] and h50[hi]<=h50[hi-3]
    if bull==bear:return 0
    x=m[i];rng=x.h-x.l;body=abs(x.c-x.o)
    if rng<=0 or rng>RANGE_MAX*av or body<BODY_MIN*av or body>BODY_MAX*av:return 0
    if abs(x.c-e20[i])>cfg.max_dist*av:return 0
    up=e20[i]>e20[i-3];dn=e20[i]<e20[i-3]
    touched=False
    for j in range(1,PULL_BARS+1):
        z=m[i-j]
        if z.l<=e20[i-j]+cfg.pull_tol*av and z.h>=e20[i-j]-cfg.pull_tol*av:
            # reject pullbacks that penetrated far through value
            if bull and z.l>=e20[i-j]-.70*av:touched=True
            elif bear and z.h<=e20[i-j]+.70*av:touched=True
    if not touched:return 0
    cp=(x.c-x.l)/rng;p=m[i-1]
    if bull and up and x.c>x.o and x.c>e20[i] and cp>=.65 and x.c>p.h:return 1
    if bear and dn and x.c<x.o and x.c<e20[i] and cp<=.35 and x.c<p.l:return -1
    return 0

def make(i,d,en,eq,peak,ls,m,a,cfg):
    av=a[i];lo=min(m[k].l for k in range(max(0,i-SWING_BARS+1),i+1));hi=max(m[k].h for k in range(max(0,i-SWING_BARS+1),i+1))
    if d>0:sl=min(lo-SWING_BUF*av,en-cfg.min_sl_atr*av);dist=en-sl
    else:sl=max(hi+SWING_BUF*av,en+cfg.min_sl_atr*av);dist=sl-en
    if dist<=0:return None,'BAD',False
    if dist>MAX_SL_ATR*av:return None,'WIDE',False
    if abs(en-m[i].c)>cfg.max_dist*av:return None,'CHASE',False
    rec=eq<peak-1e-9 or ls>0;rr=cfg.rec_rr if rec else cfg.rr;tp=en+d*rr*dist
    rm=eq*riskpct(eq,peak,ls);loss1=(dist+COST_PRICE)*OZ;vr=rm/loss1 if loss1>0 else 0
    vm=(eq*MARGIN_CAP*LEVERAGE)/(en*OZ);cap=vr>vm;lot=volfloor(min(vr,vm))
    if lot<=0:return None,'SMALL',cap
    return Pos(d,en,sl,sl,tp,lot,rec,m[i+1].t), 'OK',cap

def net(p,x):return p.d*(x-p.en)*OZ*p.lot-COST_PRICE*OZ*p.lot

def run(m,e20,a,h,h20,h50,ha,hend,start,end,cfg):
    eq=peak=mn=BASE;dd=0.;ls=0;pos=None
    tr=w=l=be=rec=oa=mc=sw=sc=0;maxlot=0.;fo='-';pa='-';peq=0.;st=m[start].t
    # A trade closed within bar j cannot be re-entered from a signal that was only known later inside j.
    just_closed=False
    for j in range(max(start,81),min(end,len(m)-1)):
        b=m[j];just_closed=False
        if pos:
            x=None;out=None
            if pos.d>0:
                if b.o<=pos.sl:x=b.o;out='SL'
                elif b.o>=pos.tp:x=b.o;out='TP'
                else:
                    hs=b.l<=pos.sl;ht=b.h>=pos.tp
                    if hs and ht:x=pos.sl;out='SL'
                    elif hs:x=pos.sl;out='SL'
                    elif ht:x=pos.tp;out='TP'
            else:
                if b.o>=pos.sl:x=b.o;out='SL'
                elif b.o<=pos.tp:x=b.o;out='TP'
                else:
                    hs=b.h>=pos.sl;ht=b.l<=pos.tp
                    if hs and ht:x=pos.sl;out='SL'
                    elif hs:x=pos.sl;out='SL'
                    elif ht:x=pos.tp;out='TP'
            if x is not None:
                pnl=net(pos,x);eq+=pnl;mn=min(mn,eq);just_closed=True
                if out=='TP' and pnl>0:
                    w+=1;ls=0;peak=max(peak,eq)
                    if pos.lot>=MILESTONE-1e-12:
                        return R('PASS_1LOT',st,b.t,(b.t-st).total_seconds()/86400,eq,peak,mn,dd*100,max(maxlot,pos.lot),tr,w,l,be,rec,oa,fo,b.t.isoformat(),eq,mc,sw,sc)
                else:
                    l+=1;ls+=1
                    if pos.be:be+=1
                if eq<=0:return R('BUST',st,b.t,(b.t-st).total_seconds()/86400,eq,peak,mn,100.,maxlot,tr,w,l,be,rec,oa,fo,'-',0.,mc,sw,sc)
                dd=max(dd,(peak-eq)/peak if peak>0 else 1);pos=None
            else:
                worst=b.l if pos.d>0 else b.h;flt=eq+pos.d*(worst-pos.en)*OZ*pos.lot-COST_PRICE*OZ*pos.lot;mn=min(mn,flt);dd=max(dd,(peak-flt)/peak if peak>0 else 1)
                # BE can only arm from information known at THIS BAR CLOSE, so it applies next bar.
                initial_r=abs(pos.en-pos.initial_sl)
                close_r=pos.d*(b.c-pos.en)/initial_r if initial_r>0 else 0
                if not pos.be and close_r>=BE_TRIGGER_R:
                    newsl=pos.en+pos.d*BE_LOCK_R*initial_r
                    if (pos.d>0 and newsl>pos.sl) or (pos.d<0 and newsl<pos.sl):pos.sl=newsl;pos.be=True
        if pos is None and not just_closed and j+1<end:
            d=sig(j,m,e20,a,h,h20,h50,ha,hend,cfg)
            if not d:continue
            p,why,cap=make(j,d,m[j+1].o,eq,peak,ls,m,a,cfg)
            if cap:mc+=1
            if not p:
                if why=='WIDE':sw+=1
                elif why=='CHASE':sc+=1
                continue
            pos=p;tr+=1;maxlot=max(maxlot,p.lot)
            if p.rec:rec+=1
            if p.lot>=MILESTONE-1e-12:
                oa+=1
                if fo=='-':fo=p.opened.isoformat()
    fe=eq
    if pos:
        z=m[min(end-1,len(m)-1)];fe=eq+pos.d*(z.c-pos.en)*OZ*pos.lot-COST_PRICE*OZ*pos.lot;mn=min(mn,fe);dd=max(dd,(peak-fe)/peak if peak>0 else 1)
    last=m[min(end-1,len(m)-1)].t
    return R('DATA_END',st,last,(last-st).total_seconds()/86400,fe,peak,mn,dd*100,maxlot,tr,w,l,be,rec,oa,fo,'-',0.,mc,sw,sc)

def qidx(n,f,floor):return max(floor,min(n-2,int(f*(n-1))))
def rank(rs):
    ps=sum(x.status=='PASS_1LOT' for x in rs);bs=sum(x.status=='BUST' for x in rs);g=statistics.median(math.log(max(.01,x.eq)/BASE) for x in rs);ml=statistics.median(x.maxlot for x in rs);md=statistics.median(x.dd for x in rs)
    return(ps,-bs,g,ml,-md)

def main():
    m,rm,dm,bm=load(M15_PATH);h,rh,dh,bh=load(H1_PATH);audit('XAUUSD_M15',m,rm,dm,bm,15);audit('XAUUSD_H1',h,rh,dh,bh,60)
    print(f'DATA_SHA256 M15={sha(M15_PATH)} H1={sha(H1_PATH)}',flush=True)
    print('ASSUMPTIONS start=20 trueEquityCompound volumeStepStd=.0001 noHardMaxLot riskNormal=4% recovery=2% loss1=2.5% loss2=1.5% loss3+=0.75% cost=$0.30/oz leverage=1:500 marginCap=35% PASS=TP_at_1.00_standard_lot',flush=True)
    print('SIGNAL H1 EMA20/50+ATR regime; M15 EMA20+ATR pullback/reclaim; liquid-hours new entries; bar-close BE; no oscillators; no artificial cooldown',flush=True)
    e=ema([x.c for x in m],20);a=atr(m,14);h20=ema([x.c for x in h],20);h50=ema([x.c for x in h],50);ha=atr(h,14);hend=[x.t+timedelta(hours=1) for x in h]
    cfgs=[Cfg(sep,pull,dist,sl,rr) for sep in (.10,.18) for pull in (.08,.14) for dist in (.25,.35) for sl in (1.00,1.20) for rr in (1.30,1.50)]
    n=len(m);floor=max(1000,int(n*.01));cs=[qidx(n,f,floor) for f in (.03,.09,.15,.21)];ce=qidx(n,.34,floor);best=None
    print(f'CAL_CONFIGS {len(cfgs)} CAL_END={m[ce].t.isoformat()}',flush=True)
    for k,c in enumerate(cfgs,1):
        rs=[run(m,e,a,h,h20,h50,ha,hend,s,ce,c) for s in cs];rk=rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        if k%8==0 or k==len(cfgs):print(f'CAL_PROGRESS {k}/{len(cfgs)} best={best[0]} cfg={best[1]}',flush=True)
    cfg=best[1];print(f'BEST_CFG {cfg} recoveryRR={cfg.rec_rr:.2f}',flush=True)
    starts=[qidx(n,f,floor) for f in (.36,.40,.44,.48,.52,.56,.60,.64,.68,.72)];rs=[]
    for j,s in enumerate(starts,1):
        r=run(m,e,a,h,h20,h50,ha,hend,s,n,cfg);rs.append(r);wr=100*r.wins/max(1,r.wins+r.losses)
        print(f'XAU_TEST{j:02d} start={r.start.isoformat()} status={r.status} end={r.end.isoformat()} days={r.days:.2f} finalEq={r.eq:.2f} peakEq={r.peak:.2f} minEq={r.min_eq:.2f} maxDD={r.dd:.2f}% maxLotStd={r.maxlot:.4f} trades={r.trades} TP={r.wins} lossExits={r.losses} BEexits={r.be_exits} winRate={wr:.2f}% recTrades={r.rec_trades} oneLotAttempts={r.one_attempts} first1Lot={r.first_one} passAt={r.pass_at} passEq={r.pass_eq:.2f} marginCaps={r.margin_caps} skipWide={r.skip_wide} skipChase={r.skip_chase}',flush=True)
    print(f'XAU_FINAL PASS_1LOT={sum(x.status=="PASS_1LOT" for x in rs)}/10 BUST={sum(x.status=="BUST" for x in rs)}/10 DATA_END={sum(x.status=="DATA_END" for x in rs)}/10 MED_FINAL_EQ={statistics.median(x.eq for x in rs):.2f} MED_MAX_LOT_STD={statistics.median(x.maxlot for x in rs):.4f} MAX_LOT_STD={max(x.maxlot for x in rs):.4f} MED_DD={statistics.median(x.dd for x in rs):.2f}% TRADES={sum(x.trades for x in rs)} TP={sum(x.wins for x in rs)} LOSS_EXITS={sum(x.losses for x in rs)} BEST_CFG={cfg}',flush=True)
if __name__=='__main__':main()
