#!/usr/bin/env python3
"""XAU V4 — source-aligned H1/M15 true compounding research.

Key data repair: H1 bias bars are derived from the SAME deduplicated M15 source,
not from the sparse independent H1 file. This prevents stale/misaligned HTF bias.
Indicators remain minimal: derived-H1 EMA20/EMA50, M15 EMA20, M15 ATR14.
"""
from __future__ import annotations
import bisect,math,statistics
from dataclasses import dataclass
from datetime import timedelta
import xau_v2_growth_compound_to_1lot_10x as core

core.BE_TRIGGER_R=.85;core.BE_LOCK_R=.05
MAX_SL_ATR=2.0

@dataclass(frozen=True)
class Cfg:
    pull_tol:float;max_dist:float;min_sl_atr:float;rr:float;trigger:str
    @property
    def rec_rr(self):return self.rr+.20

def derive_h1(m):
    groups={}
    for z in m:
        k=z.t.replace(minute=0,second=0,microsecond=0)
        groups.setdefault(k,[]).append(z)
    out=[];dropped=0
    for k in sorted(groups):
        xs=sorted(groups[k],key=lambda x:x.t)
        # Normal gold hour has four M15 bars. Permit 3 around session edges, never 1-2.
        if len(xs)<3:dropped+=1;continue
        out.append(core.Bar(k,xs[0].o,max(x.h for x in xs),min(x.l for x in xs),xs[-1].c,sum(x.v for x in xs)))
    print(f'DERIVED_H1 rows={len(out)} droppedPartialHours={dropped} range={out[0].t.isoformat()}->{out[-1].t.isoformat()}',flush=True)
    return out

def liquid(t):
    if t.weekday()>=5:return False
    if not(5<=t.hour<=21):return False
    if t.weekday()==4 and t.hour>=19:return False
    return True

def sig(i,m,e20,a,h,h20,h50,ha,hend,cfg):
    if i<80 or not liquid(m[i].t):return 0
    av=a[i]
    if not math.isfinite(av) or av<=0:return 0
    hi=bisect.bisect_right(hend,m[i].t+timedelta(minutes=15))-1
    if hi<60:return 0
    bull=h20[hi]>h50[hi] and h[hi].c>h20[hi] and h20[hi]>h20[hi-3] and h50[hi]>=h50[hi-3]
    bear=h20[hi]<h50[hi] and h[hi].c<h20[hi] and h20[hi]<h20[hi-3] and h50[hi]<=h50[hi-3]
    if bull==bear:return 0
    x=m[i];p=m[i-1];rng=x.h-x.l;body=abs(x.c-x.o)
    if rng<=0 or rng>1.08*av or body<.12*av or body>.68*av:return 0
    if abs(x.c-e20[i])>cfg.max_dist*av:return 0
    up=e20[i]>e20[i-3];dn=e20[i]<e20[i-3]
    touched=False
    for j in range(1,5):
        z=m[i-j];near=z.l<=e20[i-j]+cfg.pull_tol*av and z.h>=e20[i-j]-cfg.pull_tol*av
        if near:
            if bull and z.l>=e20[i-j]-.85*av:touched=True
            if bear and z.h<=e20[i-j]+.85*av:touched=True
    if not touched:return 0
    cp=(x.c-x.l)/rng
    basic_long=bull and up and x.c>x.o and x.c>e20[i] and x.c>=p.c and cp>=.60
    basic_short=bear and dn and x.c<x.o and x.c<e20[i] and x.c<=p.c and cp<=.40
    if cfg.trigger=='basic':
        return 1 if basic_long else (-1 if basic_short else 0)
    lower_wick=min(x.o,x.c)-x.l;upper_wick=x.h-max(x.o,x.c)
    bull_pin=lower_wick>=max(.22*av,1.15*body) and cp>=.65
    bear_pin=upper_wick>=max(.22*av,1.15*body) and cp<=.35
    bull_engulf=p.c<p.o and x.c>x.o and x.c>=p.o and x.o<=p.c+.08*av
    bear_engulf=p.c>p.o and x.c<x.o and x.c<=p.o and x.o>=p.c-.08*av
    if basic_long and (bull_pin or bull_engulf):return 1
    if basic_short and (bear_pin or bear_engulf):return -1
    return 0

def make(i,d,en,eq,peak,ls,m,a,cfg):
    av=a[i];lo=min(m[k].l for k in range(max(0,i-3),i+1));hi=max(m[k].h for k in range(max(0,i-3),i+1))
    if d>0:sl=min(lo-.10*av,en-cfg.min_sl_atr*av);dist=en-sl
    else:sl=max(hi+.10*av,en+cfg.min_sl_atr*av);dist=sl-en
    if dist<=0:return None,'BAD',False
    if dist>MAX_SL_ATR*av:return None,'WIDE',False
    if abs(en-m[i].c)>cfg.max_dist*av:return None,'CHASE',False
    rec=eq<peak-1e-9 or ls>0;tp=en+d*(cfg.rec_rr if rec else cfg.rr)*dist
    rm=eq*core.riskpct(eq,peak,ls);vr=rm/((dist+core.COST_PRICE)*core.OZ)
    vm=(eq*core.MARGIN_CAP*core.LEVERAGE)/(en*core.OZ);cap=vr>vm;lot=core.volfloor(min(vr,vm))
    if lot<=0:return None,'SMALL',cap
    return core.Pos(d,en,sl,sl,tp,lot,rec,m[i+1].t),'OK',cap

core.sig=sig;core.make=make

def main():
    m,raw,dups,bad=core.load(core.M15_PATH);core.audit('XAUUSD_M15',m,raw,dups,bad,15);h=derive_h1(m)
    print(f'DATA_SHA256 M15={core.sha(core.M15_PATH)}',flush=True)
    print('ASSUMPTIONS start=20 trueEquityCompound noHardMaxLot riskNormal=4% recovery=2% loss1=2.5% loss2=1.5% loss3+=0.75% cost=$0.30/oz leverage=1:500 marginCap=35% PASS=TP_at_1.00_standard_lot',flush=True)
    print('SIGNAL SAME_SOURCE derived H1 EMA20/50 + M15 EMA20/ATR14 pullback/reclaim; basic or reversal price trigger; BE=.85R',flush=True)
    e=core.ema([x.c for x in m],20);a=core.atr(m,14);h20=core.ema([x.c for x in h],20);h50=core.ema([x.c for x in h],50);ha=core.atr(h,14);hend=[x.t+timedelta(hours=1) for x in h]
    cfgs=[Cfg(p,d,s,rr,t) for p in (.10,.18) for d in (.30,.40) for s in (1.0,1.2) for rr in (1.2,1.4,1.6) for t in ('basic','reversal')]
    n=len(m);floor=max(1000,int(n*.01));cs=[core.qidx(n,f,floor) for f in (.03,.09,.15,.21)];ce=core.qidx(n,.34,floor);best=None
    print(f'CAL_CONFIGS {len(cfgs)} CAL_END={m[ce].t.isoformat()}',flush=True)
    for k,c in enumerate(cfgs,1):
        rs=[core.run(m,e,a,h,h20,h50,ha,hend,s,ce,c) for s in cs];rk=core.rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        if k%12==0 or k==len(cfgs):print(f'CAL_PROGRESS {k}/{len(cfgs)} best={best[0]} cfg={best[1]}',flush=True)
    cfg=best[1];print(f'BEST_CFG {cfg} recoveryRR={cfg.rec_rr:.2f}',flush=True)
    starts=[core.qidx(n,f,floor) for f in (.36,.40,.44,.48,.52,.56,.60,.64,.68,.72)];rs=[]
    for j,s in enumerate(starts,1):
        r=core.run(m,e,a,h,h20,h50,ha,hend,s,n,cfg);rs.append(r);wr=100*r.wins/max(1,r.wins+r.losses)
        print(f'XAU_TEST{j:02d} start={r.start.isoformat()} status={r.status} end={r.end.isoformat()} days={r.days:.2f} finalEq={r.eq:.2f} peakEq={r.peak:.2f} minEq={r.min_eq:.2f} maxDD={r.dd:.2f}% maxLotStd={r.maxlot:.4f} trades={r.trades} TP={r.wins} lossExits={r.losses} BEexits={r.be_exits} winRate={wr:.2f}% recTrades={r.rec_trades} oneLotAttempts={r.one_attempts} first1Lot={r.first_one} passAt={r.pass_at} passEq={r.pass_eq:.2f} marginCaps={r.margin_caps} skipWide={r.skip_wide} skipChase={r.skip_chase}',flush=True)
    print(f'XAU_FINAL PASS_1LOT={sum(x.status=="PASS_1LOT" for x in rs)}/10 BUST={sum(x.status=="BUST" for x in rs)}/10 DATA_END={sum(x.status=="DATA_END" for x in rs)}/10 MED_FINAL_EQ={statistics.median(x.eq for x in rs):.2f} MED_MAX_LOT_STD={statistics.median(x.maxlot for x in rs):.4f} MAX_LOT_STD={max(x.maxlot for x in rs):.4f} MED_DD={statistics.median(x.dd for x in rs):.2f}% TRADES={sum(x.trades for x in rs)} TP={sum(x.wins for x in rs)} LOSS_EXITS={sum(x.losses for x in rs)} BEST_CFG={cfg}',flush=True)
if __name__=='__main__':main()
