#!/usr/bin/env python3
"""BTC V28 — adaptive LONG/SHORT + pullback/reclaim entry, maximize PASS/30 over 60-day windows.

Locked execution:
- BTC only 24/7
- start $20; one position; 0.02 -> 1.00; +0.01 only after actual TP
- TP = 300 BTC price units
- no SL / Smart Cut / trailing / forced timeout close
- no cooldown / daily cap / session filter / news filter
- after TP there is no time restriction; next M5 is eligible, but entry waits until setup is clean
- anti-FOMO: never chase if price is too extended from adaptive value or bar expansion is abnormal
- objective: maximize PASS count across 30 random 60-day windows; no streak requirement

Core change from V27:
1) Direction is adaptive by regime instead of one fixed EMA pair.
2) Strong trend: follow EMA8/20 structure + slopes.
3) Slower trend: use EMA12/36 structure to avoid flipping on noise.
4) Mixed regime: multi-horizon vote, but a clean pullback/reclaim is required.
5) Entry location matters: trend direction alone is insufficient; enter near value after retrace/reclaim,
   while avoiding already-extended chase bars.
"""
from __future__ import annotations
import argparse, itertools, os, random, statistics, sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dual_xau_btc_v21_vwap_unbounded as v21
import mt5_progressive_tp_backtest_v8 as b8

MAX_DAYS=60.0; TARGET_TP=99; TP_PRICE=300.0; START_BAL=20.0; LOT0=.02
MAX_WINDOWS=30; WARM=700

@dataclass(frozen=True)
class Cfg:
    vwap_win:int
    trend_sep:float
    min_score:float
    max_dist:float
    max_bar:float
    reclaim:float
    pullback:float

@dataclass
class Result:
    tps:int; done:bool; bust:bool; reason:str; balance:float; dd:float
    trades:int; hold:int; lot:float; when:str; days:float; cfg:object


def cfgs():
    # Focus search on direction quality and entry location, not arbitrary indicator combinations.
    for vw,ts,ms,md,mb,rc,pb in itertools.product(
        (48,96),
        (0.10,0.18,0.28),
        (2.0,2.6,3.2),
        (0.70,0.95,1.20,1.45),
        (1.55,1.90),
        (0.00,0.08,0.16),
        (0.10,0.22),
    ):
        yield Cfg(vw,ts,ms,md,mb,rc,pb)


def seed_value(cli):
    if cli is not None:return cli
    rid=os.getenv('GITHUB_RUN_ID');att=os.getenv('GITHUB_RUN_ATTEMPT','1')
    if rid and rid.isdigit():return int(rid)*100+int(att)
    return 280001


def candidate_starts(bars,seed,n=MAX_WINDOWS):
    bars60=int(MAX_DAYS*24*12);lo=WARM;hi=len(bars)-bars60-3
    if hi<=lo:raise RuntimeError('not enough BTC history')
    rng=random.Random(seed);xs=list(range(lo,hi));rng.shuffle(xs)
    out=[];gap=12*24*2
    for s in xs:
        if all(abs(s-x)>=gap for x in out):
            out.append(s)
            if len(out)>=n:break
    if len(out)<n:raise RuntimeError(f'only {len(out)} valid starts')
    return out


def sgn(x,eps=0.0):return 1 if x>eps else -1 if x<-eps else 0


def context(i,b,c,I):
    E=I['e'];V=I['v'];A=I['a'];x=b[i];atr=max(A[i],1e-9)
    e8,e20,e12,e36=E[8][i],E[20][i],E[12][i],E[36][i]
    vw=V[c.vwap_win][i]
    sep_fast=(e8-e20)/atr;sep_slow=(e12-e36)/atr
    s8=(e8-E[8][i-3])/atr;s20=(e20-E[20][i-6])/atr
    s12=(e12-E[12][i-4])/atr;s36=(e36-E[36][i-8])/atr
    vs=(vw-V[c.vwap_win][i-6])/atr
    mom3=(x.c-b[i-3].c)/atr;mom6=(x.c-b[i-6].c)/atr

    # Regime chooses which horizon deserves authority.
    if abs(sep_fast)>=c.trend_sep and sgn(sep_fast)==sgn(s8+s20):
        regime='fast'; anchor=(e8+e20+vw)/3.0
        score=(2.4*sgn(sep_fast)+1.3*sgn(s8)+0.8*sgn(s20)+0.55*sgn(vs)+0.45*sgn(mom3)+0.25*sgn(mom6))
    elif abs(sep_slow)>=c.trend_sep*0.75 and sgn(sep_slow)==sgn(s12+s36):
        regime='slow'; anchor=(e12+e36+vw)/3.0
        score=(2.1*sgn(sep_slow)+1.0*sgn(s12)+0.85*sgn(s36)+0.55*sgn(vs)+0.35*sgn(mom3)+0.35*sgn(mom6))
    else:
        regime='mixed'; anchor=(e8+e20+e36+vw)/4.0
        score=(1.15*sgn(sep_fast)+1.15*sgn(sep_slow)+0.75*sgn(s8)+0.65*sgn(s12)+0.55*sgn(vs)+0.55*sgn(mom3)+0.45*sgn(mom6))

    # Continuous strength helps distinguish true structure from tiny crosses.
    score += max(-0.8,min(0.8,sep_fast))*0.7 + max(-0.8,min(0.8,sep_slow))*0.5
    return regime,score,anchor,atr


def signal(i,b,c,I):
    if i<max(WARM,45):return 0
    x=b[i];prev=b[i-1];regime,score,value,atr=context(i,b,c,I)
    if abs(score)<c.min_score:return 0
    d=1 if score>0 else -1

    dist=(x.c-value)/atr;prev_dist=(prev.c-value)/atr
    rng=(x.h-x.l)/atr;body=abs(x.c-x.o)/atr

    # Anti-FOMO: do not chase an already extended move or abnormal expansion candle.
    if abs(dist)>c.max_dist:return 0
    if rng>c.max_bar or body>c.max_bar*0.72:return 0
    if d>0 and dist>c.max_dist*0.72:return 0
    if d<0 and dist<-c.max_dist*0.72:return 0

    # Entry location: prefer retrace then reclaim / renewed movement from value.
    # In a clean strong trend, a shallow pullback is enough; mixed regimes require clearer reclaim.
    near=abs(dist)<=max(c.pullback,c.max_dist*0.45)
    if not near:return 0
    if d>0:
        reclaim=(x.c>=x.o and x.c>=prev.c-c.reclaim*atr) or (prev_dist<0<=dist)
        shallow=(regime!='mixed' and dist<=c.pullback and x.c>=prev.c)
    else:
        reclaim=(x.c<=x.o and x.c<=prev.c+c.reclaim*atr) or (prev_dist>0>=dist)
        shallow=(regime!='mixed' and dist>=-c.pullback and x.c<=prev.c)
    if not (reclaim or shallow):return 0
    return d


def run_window(full,s,c):
    bars60=int(MAX_DAYS*24*12);a=s-WARM;z=min(len(full),s+bars60+3)
    w=full[a:z];I=v21.prep(w);start_idx=WARM
    bal=START_BAL;peak=START_BAL;dd=0.;lot=LOT0;tps=tr=mh=0;pos=None
    st=v21.DT(full[s].dt);deadline=st+timedelta(days=MAX_DAYS);when=full[s].dt
    for i in range(start_idx,len(w)):
        bar=w[i];now=v21.DT(bar.dt)
        if now>deadline:return Result(tps,False,False,'TIME_LIMIT',bal,dd*100,tr,mh,lot,when,MAX_DAYS,c)
        if pos is None:
            d=signal(i-1,w,c,I)
            if not d:continue
            pos=(d,bar.o,lot,i);tr+=1
        d,en,L,ei=pos;mh=max(mh,i-ei+1)
        adverse=max(0.,en-bar.l) if d>0 else max(0.,bar.h-en)
        flt=bal-adverse*L;dd=max(dd,(peak-flt)/peak)
        if flt<=0:return Result(tps,False,True,'BUST',0.,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
        tar=en+d*TP_PRICE;hit=bar.h>=tar if d>0 else bar.l<=tar
        if hit:
            bal+=TP_PRICE*L;peak=max(peak,bal);tps+=1;when=bar.dt
            if L>=1.-1e-9:
                ok=tps==TARGET_TP and now<=deadline
                return Result(tps,ok,False,'PASS99' if ok else 'CHAIN_ERROR',bal,dd*100,tr,mh,L,bar.dt,(now-st).total_seconds()/86400,c)
            lot=round(L+.01,2);pos=None
    return Result(tps,False,False,'DATA_END',bal,dd*100,tr,mh,lot,when,(v21.DT(w[-1].dt)-st).total_seconds()/86400,c)


def rank(rs):
    passes=sum(r.done for r in rs);busts=sum(r.bust for r in rs);tp=sum(r.tps for r in rs)
    med=statistics.median(r.tps for r in rs);dd=statistics.median(r.dd for r in rs)
    near=sum(r.tps>=80 for r in rs)
    return (passes,near,tp,med,-busts,-dd)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int);a=ap.parse_args()
    seed=seed_value(a.seed);bars=b8.load();starts=candidate_starts(bars,seed);configs=list(cfgs())
    print('=== BTC V28 ADAPTIVE REGIME + PULLBACK/RECLAIM / MAX PASS 30x60D ===',flush=True)
    print(f'SEED {seed} range {bars[0].dt} -> {bars[-1].dt} bars={len(bars)} windows=30 configs={len(configs)}',flush=True)
    print('RULES 24/7 unlimitedTP/day TP300 noSL noCut noCooldown noSession noNews exact60d=True',flush=True)
    print('ENTRY adaptive direction + clean pullback/reclaim + anti-FOMO; objective=max PASS/30',flush=True)
    bestc=bestr=bestrk=None
    for n,c in enumerate(configs,1):
        rs=[run_window(bars,s,c) for s in starts];rk=rank(rs)
        if bestrk is None or rk>bestrk:
            bestc,bestr,bestrk=c,rs,rk
            print(f'NEW_BEST cfg#{n} PASS={rk[0]}/30 NEAR80={rk[1]}/30 TP_SUM={rk[2]} MED_TP={rk[3]:.1f} BUST={sum(r.bust for r in rs)}/30 CFG={c}',flush=True)
        if n%150==0:print(f'PROGRESS {n}/{len(configs)} BEST_PASS={bestrk[0]}/30 TP_SUM={bestrk[2]}',flush=True)
    assert bestc is not None
    p=sum(r.done for r in bestr);bu=sum(r.bust for r in bestr)
    print('=== BEST CONFIG WINDOW DETAIL ===',flush=True)
    for j,(s,r) in enumerate(zip(starts,bestr),1):
        state='PASS' if r.done else 'FAIL'
        print(f'BTC_WINDOW{j:02d}={state} start={bars[s].dt} TP={r.tps}/99 reason={r.reason} days={r.days:.2f} DD={r.dd:.2f}% lot={r.lot:.2f} trades={r.trades} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS={p}/30 FAIL={30-p}/30 BUST={bu}/30 NEAR80={sum(r.tps>=80 for r in bestr)}/30 TP_SUM={sum(r.tps for r in bestr)} MED_TP={statistics.median(r.tps for r in bestr):.1f} BEST_CFG={bestc}',flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
