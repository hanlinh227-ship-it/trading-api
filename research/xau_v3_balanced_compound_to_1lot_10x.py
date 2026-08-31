#!/usr/bin/env python3
"""XAU V3 balanced true-compound research.

V1: enough trades but negative edge at 2R.
V2: over-filtered (almost no trades).
V3 deliberately uses the middle ground with ONLY EMA50 H1, EMA20 M15, ATR14 M15
and raw candle/pullback behavior. No RSI/MACD/ADX/oscillator stack.
"""
from __future__ import annotations
import bisect,math,statistics
from dataclasses import dataclass
from datetime import timedelta
import xau_v2_growth_compound_to_1lot_10x as core

# Keep V2's true compounding/recovery and realistic cost/margin model.
core.BE_TRIGGER_R=.85
core.BE_LOCK_R=.05
MAX_SL_ATR=2.00

@dataclass(frozen=True)
class Cfg:
    pull_tol:float
    max_dist:float
    min_sl_atr:float
    rr:float
    h1_slope_bars:int
    @property
    def rec_rr(self):return self.rr+.20

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
    if hi<60+cfg.h1_slope_bars:return 0
    # Simple H1 authority: two completed closes on same side of EMA50 + EMA50 slope.
    bull=h[hi].c>h50[hi] and h[hi-1].c>h50[hi-1] and h50[hi]>h50[hi-cfg.h1_slope_bars]
    bear=h[hi].c<h50[hi] and h[hi-1].c<h50[hi-1] and h50[hi]<h50[hi-cfg.h1_slope_bars]
    if bull==bear:return 0
    x=m[i];rng=x.h-x.l;body=abs(x.c-x.o)
    if rng<=0 or rng>1.08*av or body<.14*av or body>.68*av:return 0
    if abs(x.c-e20[i])>cfg.max_dist*av:return 0
    up=e20[i]>e20[i-3];dn=e20[i]<e20[i-3]
    touched=False
    for j in range(1,5):
        z=m[i-j]
        near=z.l<=e20[i-j]+cfg.pull_tol*av and z.h>=e20[i-j]-cfg.pull_tol*av
        if near:
            if bull and z.l>=e20[i-j]-.85*av:touched=True
            if bear and z.h<=e20[i-j]+.85*av:touched=True
    if not touched:return 0
    cp=(x.c-x.l)/rng;p=m[i-1]
    if bull and up and x.c>x.o and x.c>e20[i] and x.c>=p.c and cp>=.60:return 1
    if bear and dn and x.c<x.o and x.c<e20[i] and x.c<=p.c and cp<=.40:return -1
    return 0

def make(i,d,en,eq,peak,ls,m,a,cfg):
    av=a[i];lo=min(m[k].l for k in range(max(0,i-3),i+1));hi=max(m[k].h for k in range(max(0,i-3),i+1))
    if d>0:sl=min(lo-.10*av,en-cfg.min_sl_atr*av);dist=en-sl
    else:sl=max(hi+.10*av,en+cfg.min_sl_atr*av);dist=sl-en
    if dist<=0:return None,'BAD',False
    if dist>MAX_SL_ATR*av:return None,'WIDE',False
    if abs(en-m[i].c)>cfg.max_dist*av:return None,'CHASE',False
    rec=eq<peak-1e-9 or ls>0;tp=en+d*(cfg.rec_rr if rec else cfg.rr)*dist
    rm=eq*core.riskpct(eq,peak,ls);loss1=(dist+core.COST_PRICE)*core.OZ;vr=rm/loss1 if loss1>0 else 0
    vm=(eq*core.MARGIN_CAP*core.LEVERAGE)/(en*core.OZ);cap=vr>vm;lot=core.volfloor(min(vr,vm))
    if lot<=0:return None,'SMALL',cap
    return core.Pos(d,en,sl,sl,tp,lot,rec,m[i+1].t),'OK',cap

# Inject only the entry/SL geometry into the already-audited V2 lifecycle/compounding runner.
core.sig=sig
core.make=make

def rank(rs):return core.rank(rs)

def main():
    m,rm,dm,bm=core.load(core.M15_PATH);h,rh,dh,bh=core.load(core.H1_PATH)
    core.audit('XAUUSD_M15',m,rm,dm,bm,15);core.audit('XAUUSD_H1',h,rh,dh,bh,60)
    print(f'DATA_SHA256 M15={core.sha(core.M15_PATH)} H1={core.sha(core.H1_PATH)}',flush=True)
    print('ASSUMPTIONS start=20 trueEquityCompound noHardMaxLot riskNormal=4% recovery=2% loss1=2.5% loss2=1.5% loss3+=0.75% cost=$0.30/oz leverage=1:500 marginCap=35% PASS=TP_at_1.00_standard_lot',flush=True)
    print('SIGNAL EMA50-H1 trend + EMA20-M15 pullback/reclaim + ATR14-M15; liquid-hours; BE=.85R; no oscillator stack',flush=True)
    e=core.ema([x.c for x in m],20);a=core.atr(m,14);h20=core.ema([x.c for x in h],20);h50=core.ema([x.c for x in h],50);ha=core.atr(h,14);hend=[x.t+timedelta(hours=1) for x in h]
    cfgs=[Cfg(p,d,s,rr,hs) for p in (.08,.16) for d in (.28,.38) for s in (1.00,1.20) for rr in (1.20,1.40,1.60) for hs in (3,6)]
    n=len(m);floor=max(1000,int(n*.01));cs=[core.qidx(n,f,floor) for f in (.03,.09,.15,.21)];ce=core.qidx(n,.34,floor);best=None
    print(f'CAL_CONFIGS {len(cfgs)} CAL_END={m[ce].t.isoformat()}',flush=True)
    for k,c in enumerate(cfgs,1):
        rs=[core.run(m,e,a,h,h20,h50,ha,hend,s,ce,c) for s in cs];rk=rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        if k%12==0 or k==len(cfgs):print(f'CAL_PROGRESS {k}/{len(cfgs)} best={best[0]} cfg={best[1]}',flush=True)
    cfg=best[1];print(f'BEST_CFG {cfg} recoveryRR={cfg.rec_rr:.2f}',flush=True)
    starts=[core.qidx(n,f,floor) for f in (.36,.40,.44,.48,.52,.56,.60,.64,.68,.72)];rs=[]
    for j,s in enumerate(starts,1):
        r=core.run(m,e,a,h,h20,h50,ha,hend,s,n,cfg);rs.append(r);wr=100*r.wins/max(1,r.wins+r.losses)
        print(f'XAU_TEST{j:02d} start={r.start.isoformat()} status={r.status} end={r.end.isoformat()} days={r.days:.2f} finalEq={r.eq:.2f} peakEq={r.peak:.2f} minEq={r.min_eq:.2f} maxDD={r.dd:.2f}% maxLotStd={r.maxlot:.4f} trades={r.trades} TP={r.wins} lossExits={r.losses} BEexits={r.be_exits} winRate={wr:.2f}% recTrades={r.rec_trades} oneLotAttempts={r.one_attempts} first1Lot={r.first_one} passAt={r.pass_at} passEq={r.pass_eq:.2f} marginCaps={r.margin_caps} skipWide={r.skip_wide} skipChase={r.skip_chase}',flush=True)
    print(f'XAU_FINAL PASS_1LOT={sum(x.status=="PASS_1LOT" for x in rs)}/10 BUST={sum(x.status=="BUST" for x in rs)}/10 DATA_END={sum(x.status=="DATA_END" for x in rs)}/10 MED_FINAL_EQ={statistics.median(x.eq for x in rs):.2f} MED_MAX_LOT_STD={statistics.median(x.maxlot for x in rs):.4f} MAX_LOT_STD={max(x.maxlot for x in rs):.4f} MED_DD={statistics.median(x.dd for x in rs):.2f}% TRADES={sum(x.trades for x in rs)} TP={sum(x.wins for x in rs)} LOSS_EXITS={sum(x.losses for x in rs)} BEST_CFG={cfg}',flush=True)
if __name__=='__main__':main()
