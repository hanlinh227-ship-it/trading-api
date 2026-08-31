#!/usr/bin/env python3
"""BTC V31 — phase-aware target-reachability entry on complete Binance M5.
Locked: $20, BTC TP=300 price units, one position, 0.02->1.00 after TP only,
no SL/cut/trailing/cooldown/session/news/daily cap/timeout close.
V31 focuses on the observed V30 failure mode: fragile early stages.
"""
from __future__ import annotations
import itertools,statistics,sys
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import btc_binance_m5_full_loader as data
import btc_v30_complete_data_quality_entry_10x as v30
import dual_xau_btc_v21_vwap_unbounded as v21

@dataclass(frozen=True)
class Cfg:
    early_score:float; early_dist:float; early_confirm:float; early_atr:float
    mid_score:float; mid_dist:float; late_score:float

@dataclass
class R:
    tps:int;done:bool;bust:bool;reason:str;bal:float;dd:float;trades:int;lot:float;days:float;when:str

def cfgs():
    for z in itertools.product((6.4,7.2),(.38,.52),(.04,.08),(90.,130.),(5.4,6.0),(.65,.85),(4.8,5.4)):
        yield Cfg(*z)

def phase(lot):
    if lot<=.10+1e-9:return 'early'
    if lot<=.50+1e-9:return 'mid'
    return 'late'

def signal(i,b,c,I,lot):
    if i<v30.WARM:return 0
    sc,val,atr=v30.authority(i,b,I);ph=phase(lot)
    if ph=='early':
        need=c.early_score;md=c.early_dist;cf=c.early_confirm
        # TP300 must be plausible, but reject hyper-volatile bars where $20 cannot absorb noise.
        if atr<c.early_atr or atr>420:return 0
    elif ph=='mid':
        need=c.mid_score;md=c.mid_dist;cf=.025
        if atr<70 or atr>650:return 0
    else:
        need=c.late_score;md=.95;cf=.015
        if atr<60 or atr>800:return 0
    if abs(sc)<need:return 0
    d=1 if sc>0 else -1;x=b[i];p=b[i-1];pp=b[i-2];E=I['e'];V=I['v']
    dist=(x.c-val)/atr;rng=(x.h-x.l)/atr;body=abs(x.c-x.o)/atr
    if abs(dist)>md or rng>1.25 or body>.85:return 0
    # Strong multi-horizon agreement. Countertrend entries are not allowed.
    if d>0:
        if not(E[8][i]>E[20][i]>E[36][i] and E[60][i]>E[150][i]):return 0
        if not(E[20][i]>E[20][i-12] and E[60][i]>E[60][i-24]):return 0
        if V[96][i]<=V[96][i-12]:return 0
    else:
        if not(E[8][i]<E[20][i]<E[36][i] and E[60][i]<E[150][i]):return 0
        if not(E[20][i]<E[20][i-12] and E[60][i]<E[60][i-24]):return 0
        if V[96][i]>=V[96][i-12]:return 0
    # Value pullback then two-step continuation. No chase after expansion.
    if d>0:
        if p.l>val+.08*atr:return 0
        if not(p.c>=val-.15*atr and p.c>=p.o):return 0
        if not(x.c>x.o and x.c>p.h+cf*atr and x.c>val):return 0
        if pp.c>p.c and pp.h>p.h:return 0
    else:
        if p.h<val-.08*atr:return 0
        if not(p.c<=val+.15*atr and p.c<=p.o):return 0
        if not(x.c<x.o and x.c<p.l-cf*atr and x.c<val):return 0
        if pp.c<p.c and pp.l<p.l:return 0
    # Immediate 300-target reachability context: recent directional excursion must support it.
    look=b[max(0,i-24):i]
    if d>0:
        if max(z.h for z in look)-min(z.l for z in look)<420:return 0
    else:
        if max(z.h for z in look)-min(z.l for z in look)<420:return 0
    return d

def run(b,start,c,I):
    bal=peak=v30.START_BAL;dd=0.;lot=v30.LOT0;tps=tr=0;pos=None;st=b[start].ts;when=b[start].dt
    for i in range(max(start,v30.WARM+2),len(b)):
        z=b[i]
        if pos is None:
            d=signal(i-1,b,c,I,lot)
            if not d:continue
            pos=(d,z.o,lot);tr+=1
        d,en,L=pos
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en);flt=bal-adverse*L
        dd=max(dd,(peak-flt)/peak)
        if flt<=0:return R(tps,False,True,'BUST',0.,dd*100,tr,L,(z.ts-st)/86400,z.dt)
        tar=en+d*v30.TP;hit=z.h>=tar if d>0 else z.l<=tar
        if hit:
            bal+=v30.TP*L;peak=max(peak,bal);tps+=1;when=z.dt
            if L>=1.-1e-9:return R(tps,tps==v30.TARGET,False,'PASS99' if tps==v30.TARGET else 'CHAIN_ERROR',bal,dd*100,tr,L,(z.ts-st)/86400,z.dt)
            lot=round(L+.01,2);pos=None
    return R(tps,False,False,'DATA_END',bal,dd*100,tr,lot,(b[-1].ts-st)/86400,when)

def rank(rs):
    p=sum(r.done for r in rs);early=sum(r.bust and r.tps<10 for r in rs);bu=sum(r.bust for r in rs)
    worst=min(r.tps for r in rs);tp=sum(r.tps for r in rs);med=statistics.median(r.tps for r in rs)
    return (p,-early,-bu,worst,tp,med,-statistics.median(r.dd for r in rs))

def main():
    b=data.load();I=v21.prep(b);cal=v30.calibration_starts(b);cs=list(cfgs())
    print('=== BTC V31 PHASE-AWARE COMPLETE DATA / UNBOUNDED ===',flush=True)
    print('RULES $20 TP300 0.02->1.00 noSL noCut noTrailing noCooldown noTimeout 24/7',flush=True)
    best=None
    for n,c in enumerate(cs,1):
        rs=[run(b,s,c,I) for s in cal];rk=rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        if n%16==0 or n==len(cs):print(f'CAL_PROGRESS {n}/{len(cs)} best={best[0]} cfg={best[1]}',flush=True)
    rk,c,_=best;print('BEST_CFG',c,'CAL_RANK',rk,flush=True)
    starts=v30.fresh_starts(b);rs=[run(b,s,c,I) for s in starts]
    for j,(s,r) in enumerate(zip(starts,rs),1):
        print(f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} TP={r.tps}/99 days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS={sum(r.done for r in rs)}/10 BUST={sum(r.bust for r in rs)}/10 DATA_END={sum(r.reason=="DATA_END" for r in rs)}/10 TP_SUM={sum(r.tps for r in rs)} MED_TP={statistics.median(r.tps for r in rs):.1f} MAX_TP={max(r.tps for r in rs)} MIN_TP={min(r.tps for r in rs)} BEST_CFG={c}',flush=True)
if __name__=='__main__':main()
