#!/usr/bin/env python3
"""XAU V1 true-compound research backtest.

Research only. No live execution and no production state changes.

Design goals
------------
* Start with USD 20.
* True compounding: every entry recomputes standard-lot equivalent from CURRENT equity,
  current SL distance, and a fixed percentage risk budget.
* No fixed +lot ladder and no strategy hard max lot.
* Recovery is anti-martingale: risk contracts after losses; it never increases after SL.
* Minimal signal stack only: H1 EMA50 bias, M15 EMA20 pullback/reclaim, M15 ATR14.
* PASS only when a trade with >= 1.00 STANDARD XAU lot equivalent closes at TP.
* Conservative intrabar ambiguity: if TP and SL are both touched in one M15 bar, SL wins.
* No synthetic bars/fills. Gaps in source data are retained and audited.

Data is supplied by workflow from public MT5 history:
  simom1/XAUUSD-history / Gold-Cash/XAUUSD
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

BASE_EQUITY = 20.0
CONTRACT_OZ = 100.0                    # 1 standard XAU lot ~= 100 oz
VOLUME_STEP_STD = 0.0001               # 0.01 cent-lot equivalent ~= 0.0001 standard lot
MILESTONE_STD_LOT = 1.0
LEVERAGE_ASSUMPTION = 500.0            # conservative research assumption
MAX_MARGIN_PCT_EQUITY = 35.0            # broker realism; not a hard lot ceiling
ROUND_TRIP_COST_PRICE = 0.30            # $0.30/oz all-in spread+slippage proxy
BASE_RISK_PCT = 0.015                   # 1.50% of CURRENT equity
RECOVERY_RISK_PCT = 0.010               # below prior equity peak after a win
LOSS1_RISK_PCT = 0.012                  # after first consecutive SL
LOSS2_RISK_PCT = 0.009                  # after second consecutive SL
LOSS3_RISK_PCT = 0.006                  # after >=3 consecutive SL
SWING_BARS = 5
SWING_BUFFER_ATR = 0.15
MAX_SL_ATR = 2.20
BODY_MIN_ATR = 0.16
BODY_MAX_ATR = 0.68
MAX_RANGE_ATR = 1.10
PULLBACK_BARS = 4

M15_PATH = Path('research/data/XAUUSD_M15.csv')
H1_PATH = Path('research/data/XAUUSD_H1.csv')

@dataclass(frozen=True)
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float

@dataclass(frozen=True)
class Cfg:
    pull_tol_atr: float
    max_entry_dist_atr: float
    min_sl_atr: float
    normal_rr: float

    @property
    def recovery_rr(self) -> float:
        return self.normal_rr + 0.30

@dataclass
class Pos:
    direction: int
    entry: float
    sl: float
    tp: float
    lot: float
    recovery: bool
    opened_at: datetime

@dataclass
class Result:
    status: str
    start: datetime
    end: datetime
    days: float
    final_equity: float
    max_equity: float
    min_equity: float
    max_dd_pct: float
    max_lot: float
    trades: int
    wins: int
    losses: int
    recovery_trades: int
    one_lot_attempts: int
    first_one_lot_at: str
    pass_at: str
    pass_equity: float
    margin_caps: int
    skipped_wide_sl: int
    skipped_chase: int


def parse_time(s: str) -> datetime:
    s = s.strip().replace('T', ' ').replace('Z', '')
    fmts = ('%Y-%m-%d %H:%M:%S', '%Y.%m.%d %H:%M', '%Y.%m.%d %H:%M:%S', '%Y-%m-%d %H:%M')
    for f in fmts:
        try:
            return datetime.strptime(s, f).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # Numeric epoch fallback.
    try:
        x = float(s)
        if x > 10_000_000_000:
            x /= 1000.0
        return datetime.fromtimestamp(x, tz=timezone.utc)
    except Exception as e:
        raise ValueError(f'Unsupported timestamp: {s!r}') from e


def load_csv(path: Path) -> List[Bar]:
    if not path.exists():
        raise FileNotFoundError(path)
    out: List[Bar] = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames:
            raise RuntimeError(f'No CSV header in {path}')
        names = {x.strip().lower(): x for x in rd.fieldnames}
        time_key = names.get('time') or names.get('datetime') or names.get('timestamp')
        required = [names.get('open'), names.get('high'), names.get('low'), names.get('close')]
        if not time_key or any(x is None for x in required):
            raise RuntimeError(f'Unsupported columns in {path}: {rd.fieldnames}')
        vol_key = names.get('tick_volume') or names.get('volume')
        for row in rd:
            try:
                t = parse_time(row[time_key])
                o = float(row[names['open']]); h = float(row[names['high']])
                l = float(row[names['low']]); c = float(row[names['close']])
                v = float(row[vol_key]) if vol_key and row.get(vol_key) not in (None, '') else 0.0
            except Exception:
                continue
            if not (o > 0 and h >= max(o,c) and l <= min(o,c) and h >= l):
                continue
            out.append(Bar(t,o,h,l,c,v))
    out.sort(key=lambda b: b.t)
    return out


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def audit(name: str, bars: List[Bar], nominal_minutes: int) -> None:
    dup = 0; nonpos = 0; gaps = 0; max_gap = 0.0
    weekendish = 0; short_irregular = 0
    for a,b in zip(bars,bars[1:]):
        dt = (b.t-a.t).total_seconds()/60.0
        if dt == 0: dup += 1
        if dt <= 0: nonpos += 1
        if dt > nominal_minutes + 1e-9:
            gaps += 1; max_gap=max(max_gap,dt)
            if dt >= 24*60: weekendish += 1
            else: short_irregular += 1
    print(f'DATA_AUDIT {name} rows={len(bars)} range={bars[0].t.isoformat()}->{bars[-1].t.isoformat()} '
          f'duplicates={dup} nonPositive={nonpos} gapIntervals={gaps} shortGaps={short_irregular} '
          f'longGaps={weekendish} maxGapMin={max_gap:.1f}', flush=True)


def ema(vals: List[float], period: int) -> List[float]:
    out=[math.nan]*len(vals)
    if not vals: return out
    a=2.0/(period+1.0)
    x=vals[0]; out[0]=x
    for i in range(1,len(vals)):
        x=a*vals[i]+(1-a)*x
        out[i]=x
    return out


def atr_wilder(bars: List[Bar], period: int) -> List[float]:
    tr=[0.0]*len(bars)
    for i,b in enumerate(bars):
        if i==0: tr[i]=b.h-b.l
        else:
            pc=bars[i-1].c
            tr[i]=max(b.h-b.l,abs(b.h-pc),abs(b.l-pc))
    out=[math.nan]*len(bars)
    if len(bars)<period: return out
    s=sum(tr[:period])/period
    out[period-1]=s
    for i in range(period,len(bars)):
        s=(s*(period-1)+tr[i])/period
        out[i]=s
    return out


def floor_volume(v: float) -> float:
    if v < VOLUME_STEP_STD: return 0.0
    return math.floor((v+1e-12)/VOLUME_STEP_STD)*VOLUME_STEP_STD


def current_risk_pct(equity: float, peak: float, loss_streak: int) -> float:
    if loss_streak >= 3: return LOSS3_RISK_PCT
    if loss_streak == 2: return LOSS2_RISK_PCT
    if loss_streak == 1: return LOSS1_RISK_PCT
    if equity < peak - 1e-9: return RECOVERY_RISK_PCT
    return BASE_RISK_PCT


def signal(i: int, m15: List[Bar], e20: List[float], atr: List[float],
           h1: List[Bar], h1_e50: List[float], h1_end: List[datetime], cfg: Cfg) -> int:
    if i < max(80, PULLBACK_BARS+3): return 0
    a=atr[i]
    if not math.isfinite(a) or a <= 0: return 0

    sig_close=m15[i].t+timedelta(minutes=15)
    hi=bisect.bisect_right(h1_end,sig_close)-1
    if hi < 55: return 0

    hb=h1[hi]; e=h1_e50[hi]
    ep=h1_e50[hi-3]
    bull_bias=(hb.c>e and h1[hi-1].c>h1_e50[hi-1] and e>ep)
    bear_bias=(hb.c<e and h1[hi-1].c<h1_e50[hi-1] and e<ep)
    if bull_bias==bear_bias: return 0

    x=m15[i]
    rng=x.h-x.l; body=abs(x.c-x.o)
    if rng<=0 or rng>MAX_RANGE_ATR*a: return 0
    if body<BODY_MIN_ATR*a or body>BODY_MAX_ATR*a: return 0
    if abs(x.c-e20[i])>cfg.max_entry_dist_atr*a: return 0

    # EMA20 direction is the only M15 trend filter.
    m15_up=e20[i]>e20[i-3]
    m15_dn=e20[i]<e20[i-3]

    touched=False
    for j in range(1,PULLBACK_BARS+1):
        z=m15[i-j]
        if z.l<=e20[i-j]+cfg.pull_tol_atr*a and z.h>=e20[i-j]-cfg.pull_tol_atr*a:
            touched=True; break
    if not touched: return 0

    close_pos=(x.c-x.l)/rng
    p=m15[i-1]
    if bull_bias and m15_up:
        if x.c>x.o and x.c>e20[i] and x.c>=p.c and close_pos>=0.62:
            return 1
    if bear_bias and m15_dn:
        if x.c<x.o and x.c<e20[i] and x.c<=p.c and close_pos<=0.38:
            return -1
    return 0


def build_trade(i: int, d: int, entry: float, equity: float, peak: float, loss_streak: int,
                m15: List[Bar], atr: List[float], cfg: Cfg) -> Tuple[Optional[Pos],str,bool]:
    a=atr[i]
    lows=[m15[k].l for k in range(max(0,i-SWING_BARS+1),i+1)]
    highs=[m15[k].h for k in range(max(0,i-SWING_BARS+1),i+1)]
    if d>0:
        structural=min(lows)-SWING_BUFFER_ATR*a
        minstop=entry-cfg.min_sl_atr*a
        sl=min(structural,minstop)
        dist=entry-sl
    else:
        structural=max(highs)+SWING_BUFFER_ATR*a
        minstop=entry+cfg.min_sl_atr*a
        sl=max(structural,minstop)
        dist=sl-entry
    if dist<=0: return None,'BAD_SL',False
    if dist>MAX_SL_ATR*a: return None,'WIDE_SL',False

    # Next-bar open may gap away from the signal. Reject if it chases > configured value.
    if abs(entry-m15[i].c)>cfg.max_entry_dist_atr*a:
        return None,'CHASE',False

    recovery=(equity<peak-1e-9 or loss_streak>0)
    rr=cfg.recovery_rr if recovery else cfg.normal_rr
    tp=entry+d*rr*dist

    risk_pct=current_risk_pct(equity,peak,loss_streak)
    risk_money=equity*risk_pct
    loss_per_std=(dist+ROUND_TRIP_COST_PRICE)*CONTRACT_OZ
    lot_risk=risk_money/loss_per_std if loss_per_std>0 else 0.0

    # Margin realism. This only follows equity/leverage and does NOT impose a strategy max lot.
    margin_lot=(equity*MAX_MARGIN_PCT_EQUITY*LEVERAGE_ASSUMPTION)/(entry*CONTRACT_OZ)
    capped=lot_risk>margin_lot
    lot=floor_volume(min(lot_risk,margin_lot))
    if lot<=0: return None,'TOO_SMALL',capped

    return Pos(d,entry,sl,tp,lot,recovery,m15[i+1].t), 'OK', capped


def close_net(pos: Pos, exit_px: float) -> float:
    gross=pos.direction*(exit_px-pos.entry)*CONTRACT_OZ*pos.lot
    cost=ROUND_TRIP_COST_PRICE*CONTRACT_OZ*pos.lot
    return gross-cost


def run(m15: List[Bar], e20: List[float], atr: List[float], h1: List[Bar], h1_e50: List[float],
        h1_end: List[datetime], start: int, end: int, cfg: Cfg) -> Result:
    equity=BASE_EQUITY; peak=BASE_EQUITY; min_eq=BASE_EQUITY; dd=0.0
    loss_streak=0; pos: Optional[Pos]=None
    trades=wins=losses=recovery_trades=one_attempts=margin_caps=0
    skipped_wide=skipped_chase=0
    max_lot=0.0; first_one='-'; pass_at='-'; pass_equity=0.0
    st=m15[start].t; last_t=st

    for j in range(max(start,81),min(end,len(m15)-1)):
        b=m15[j]
        last_t=b.t

        if pos is not None:
            # Gap-at-open execution first.
            exit_px=None; outcome=None
            if pos.direction>0:
                if b.o<=pos.sl: exit_px=b.o; outcome='SL'
                elif b.o>=pos.tp: exit_px=b.o; outcome='TP'
                else:
                    hit_sl=b.l<=pos.sl; hit_tp=b.h>=pos.tp
                    if hit_sl and hit_tp: exit_px=pos.sl; outcome='SL'   # conservative ambiguity
                    elif hit_sl: exit_px=pos.sl; outcome='SL'
                    elif hit_tp: exit_px=pos.tp; outcome='TP'
            else:
                if b.o>=pos.sl: exit_px=b.o; outcome='SL'
                elif b.o<=pos.tp: exit_px=b.o; outcome='TP'
                else:
                    hit_sl=b.h>=pos.sl; hit_tp=b.l<=pos.tp
                    if hit_sl and hit_tp: exit_px=pos.sl; outcome='SL'
                    elif hit_sl: exit_px=pos.sl; outcome='SL'
                    elif hit_tp: exit_px=pos.tp; outcome='TP'

            if exit_px is not None:
                net=close_net(pos,exit_px)
                equity+=net
                min_eq=min(min_eq,equity)
                if outcome=='TP' and net>0:
                    wins+=1; loss_streak=0
                    if equity>peak: peak=equity
                    if pos.lot>=MILESTONE_STD_LOT-1e-12:
                        pass_at=b.t.isoformat(); pass_equity=equity
                        dd=max(dd,0.0 if peak<=0 else (peak-equity)/peak)
                        return Result('PASS_1LOT',st,b.t,(b.t-st).total_seconds()/86400,
                                      equity,peak,min_eq,dd*100,max(max_lot,pos.lot),trades,wins,losses,
                                      recovery_trades,one_attempts,first_one,pass_at,pass_equity,
                                      margin_caps,skipped_wide,skipped_chase)
                else:
                    losses+=1; loss_streak+=1
                if equity<=0:
                    return Result('BUST',st,b.t,(b.t-st).total_seconds()/86400,equity,peak,min_eq,100.0,
                                  max_lot,trades,wins,losses,recovery_trades,one_attempts,first_one,'-',0.0,
                                  margin_caps,skipped_wide,skipped_chase)
                dd=max(dd,(peak-equity)/peak if peak>0 else 1.0)
                pos=None
            else:
                # Mark worst intrabar adverse equity for DD.
                worst=b.l if pos.direction>0 else b.h
                floating=equity+pos.direction*(worst-pos.entry)*CONTRACT_OZ*pos.lot \
                         - ROUND_TRIP_COST_PRICE*CONTRACT_OZ*pos.lot
                min_eq=min(min_eq,floating)
                dd=max(dd,(peak-floating)/peak if peak>0 else 1.0)

        # Only enter if flat at the END of processing this bar, based on this closed bar,
        # with fill at NEXT M15 open. If position closed inside this bar, we deliberately
        # wait until next bar rather than pretending we knew the intrabar close sequence.
        if pos is None and j+1<end:
            d=signal(j,m15,e20,atr,h1,h1_e50,h1_end,cfg)
            if not d: continue
            entry=m15[j+1].o
            p,why,capped=build_trade(j,d,entry,equity,peak,loss_streak,m15,atr,cfg)
            if capped: margin_caps+=1
            if p is None:
                if why=='WIDE_SL': skipped_wide+=1
                elif why=='CHASE': skipped_chase+=1
                continue
            pos=p; trades+=1; max_lot=max(max_lot,p.lot)
            if p.recovery: recovery_trades+=1
            if p.lot>=MILESTONE_STD_LOT-1e-12:
                one_attempts+=1
                if first_one=='-': first_one=p.opened_at.isoformat()

    # Mark open position to final close, without inventing a TP/SL.
    final_equity=equity
    if pos is not None:
        last=m15[min(end-1,len(m15)-1)]
        final_equity=equity+pos.direction*(last.c-pos.entry)*CONTRACT_OZ*pos.lot \
                     - ROUND_TRIP_COST_PRICE*CONTRACT_OZ*pos.lot
        min_eq=min(min_eq,final_equity)
        dd=max(dd,(peak-final_equity)/peak if peak>0 else 1.0)
    last=m15[min(end-1,len(m15)-1)].t
    return Result('DATA_END',st,last,(last-st).total_seconds()/86400,final_equity,peak,min_eq,dd*100,
                  max_lot,trades,wins,losses,recovery_trades,one_attempts,first_one,'-',0.0,
                  margin_caps,skipped_wide,skipped_chase)


def quantile_index(n: int, frac: float, floor_idx: int) -> int:
    return max(floor_idx,min(n-2,int(frac*(n-1))))


def rank_results(rs: List[Result]) -> tuple:
    # Calibration objective: PASS first, then survival, then robust growth and max-lot,
    # then lower drawdown. Risk percentages are fixed and never optimized.
    passes=sum(r.status=='PASS_1LOT' for r in rs)
    busts=sum(r.status=='BUST' for r in rs)
    med_growth=statistics.median(math.log(max(0.01,r.final_equity)/BASE_EQUITY) for r in rs)
    med_lot=statistics.median(r.max_lot for r in rs)
    med_dd=statistics.median(r.max_dd_pct for r in rs)
    return (passes,-busts,med_growth,med_lot,-med_dd)


def main() -> None:
    m15=load_csv(M15_PATH); h1=load_csv(H1_PATH)
    if len(m15)<5000 or len(h1)<1000:
        raise RuntimeError(f'Insufficient data M15={len(m15)} H1={len(h1)}')
    audit('XAUUSD_M15',m15,15); audit('XAUUSD_H1',h1,60)
    print(f'DATA_SHA256 M15={file_sha(M15_PATH)} H1={file_sha(H1_PATH)}',flush=True)
    print('ASSUMPTIONS startEquity=20 standardLotOz=100 volumeStepStd=0.0001 '
          'baseRisk=1.50% loss1=1.20% loss2=0.90% loss3plus=0.60% recovery=1.00% '
          'leverage=1:500 marginCap=35% roundTripCostPrice=$0.30 noHardMaxLot milestone=TP_at_1.00_standard_lot',flush=True)
    print('SIGNAL H1_EMA50_bias + M15_EMA20_pullback_reclaim + M15_ATR14 only; next-bar-open entry; noCooldown',flush=True)

    e20=ema([b.c for b in m15],20); a14=atr_wilder(m15,14)
    h1e50=ema([b.c for b in h1],50)
    h1end=[b.t+timedelta(hours=1) for b in h1]

    configs=[Cfg(p,d,s,rr) for p in (0.10,0.16) for d in (0.30,0.40)
             for s in (1.20,1.40) for rr in (1.80,2.00)]

    n=len(m15); floor_idx=max(1000,int(n*0.01))
    # Calibration uses only early data and never sees the later validation region.
    cal_starts=[quantile_index(n,f,floor_idx) for f in (0.03,0.09,0.15,0.21)]
    cal_end=quantile_index(n,0.34,floor_idx)
    best=None
    print(f'CAL_CONFIGS {len(configs)} CAL_END={m15[cal_end].t.isoformat()}',flush=True)
    for k,c in enumerate(configs,1):
        rs=[]
        for s in cal_starts:
            e=min(cal_end,max(s+5000,cal_end))
            rs.append(run(m15,e20,a14,h1,h1e50,h1end,s,e,c))
        rk=rank_results(rs)
        if best is None or rk>best[0]: best=(rk,c,rs)
        if k%4==0 or k==len(configs):
            print(f'CAL_PROGRESS {k}/{len(configs)} bestRank={best[0]} bestCfg={best[1]}',flush=True)
    assert best is not None
    _,cfg,_=best
    print(f'BEST_CFG {cfg} recoveryRR={cfg.recovery_rr:.2f}',flush=True)

    # Ten locked validation starts determined solely by time-position, not outcomes.
    fracs=[0.36,0.40,0.44,0.48,0.52,0.56,0.60,0.64,0.68,0.72]
    starts=[quantile_index(n,f,floor_idx) for f in fracs]
    results=[]
    for j,s in enumerate(starts,1):
        r=run(m15,e20,a14,h1,h1e50,h1end,s,n,cfg); results.append(r)
        wr=(100*r.wins/(r.wins+r.losses)) if (r.wins+r.losses)>0 else 0.0
        print(f'XAU_TEST{j:02d} start={r.start.isoformat()} status={r.status} end={r.end.isoformat()} '
              f'days={r.days:.2f} finalEq={r.final_equity:.2f} peakEq={r.max_equity:.2f} minEq={r.min_equity:.2f} '
              f'maxDD={r.max_dd_pct:.2f}% maxLotStd={r.max_lot:.4f} trades={r.trades} TP={r.wins} SL={r.losses} '
              f'winRate={wr:.2f}% recoveryTrades={r.recovery_trades} oneLotAttempts={r.one_lot_attempts} '
              f'first1Lot={r.first_one_lot_at} passAt={r.pass_at} passEq={r.pass_equity:.2f} '
              f'marginCaps={r.margin_caps} skipWideSL={r.skipped_wide_sl} skipChase={r.skipped_chase}',flush=True)

    passes=sum(r.status=='PASS_1LOT' for r in results)
    busts=sum(r.status=='BUST' for r in results)
    med_eq=statistics.median(r.final_equity for r in results)
    med_lot=statistics.median(r.max_lot for r in results)
    med_dd=statistics.median(r.max_dd_pct for r in results)
    max_lot=max(r.max_lot for r in results)
    total_tr=sum(r.trades for r in results); total_w=sum(r.wins for r in results); total_l=sum(r.losses for r in results)
    print(f'XAU_FINAL PASS_1LOT={passes}/10 BUST={busts}/10 DATA_END={sum(r.status=="DATA_END" for r in results)}/10 '
          f'MED_FINAL_EQ={med_eq:.2f} MED_MAX_LOT_STD={med_lot:.4f} MAX_LOT_STD={max_lot:.4f} '
          f'MED_DD={med_dd:.2f}% TRADES={total_tr} TP={total_w} SL={total_l} BEST_CFG={cfg}',flush=True)

if __name__=='__main__':
    main()
