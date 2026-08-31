#!/usr/bin/env python3
"""BTC V34b — anti-FOMO pullback/reclaim entry + structure-protected exact-money SL.
Research only; no live/production changes.
"""
from __future__ import annotations
import itertools, statistics, sys
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import btc_binance_m5_full_loader as data
import btc_v30_complete_data_quality_entry_10x as v30
import dual_xau_btc_v21_vwap_unbounded as v21

BASE_BAL=20.0; BASE_LOT=0.02; RECOVERY_LOT=0.01; LOT_STEP=0.01
TP=300.0; MILESTONE=1.00; WARM=700

@dataclass(frozen=True)
class Cfg:
    base_score:float; high_score:float; close_dist:float; entry_dist:float
    buffer_atr:float; recovery_tp:float; recovery_sl:float

@dataclass
class R:
    done:bool; bust:bool; reason:str; balance:float; min_balance:float
    max_lot:float; current_lot:float; tp_count:int; sl_count:int
    recovery_entries:int; recovery_tps:int; trades:int; reject_fomo:int
    reject_stop:int; dd:float; days:float; when:str

def cfgs():
    for base,high,close_d,buf,rec in itertools.product(
        (5.2,5.6),(6.0,6.4),(0.38,0.48),(0.10,0.16),
        ((180.0,90.0),(240.0,120.0))):
        yield Cfg(base,high,close_d,min(0.55,close_d+0.10),buf,rec[0],rec[1])

def threshold(lot,c,recovery):
    if recovery:return max(6.2,c.high_score)
    if lot<=0.05+1e-9:return c.base_score
    if lot<=0.20+1e-9:return max(c.base_score+0.25,5.6)
    if lot<=0.50+1e-9:return c.high_score
    return c.high_score+0.25

def signal(i,b,c,I,lot,recovery):
    if i<WARM:return 0
    sc,val,atr=v30.authority(i,b,I)
    if abs(sc)<threshold(lot,c,recovery) or atr<70 or atr>620:return 0
    d=1 if sc>0 else -1
    x,p=b[i],b[i-1]; E,V=I['e'],I['v']
    close_dist=abs(x.c-val)/atr; rng=(x.h-x.l)/atr; body=abs(x.c-x.o)/atr
    if close_dist>c.close_dist or rng>1.00 or body>0.62:return 0
    if d>0:
        if not(E[8][i]>E[20][i]>E[36][i] and E[60][i]>E[150][i]):return 0
        if not(E[20][i]>E[20][i-8] and E[60][i]>E[60][i-20]):return 0
        if V[96][i]<=V[96][i-10]:return 0
    else:
        if not(E[8][i]<E[20][i]<E[36][i] and E[60][i]<E[150][i]):return 0
        if not(E[20][i]<E[20][i-8] and E[60][i]<E[60][i-20]):return 0
        if V[96][i]>=V[96][i-10]:return 0
    pull=b[i-3:i]
    if d>0:
        if min(z.l for z in pull)>val+0.08*atr:return 0
        if not(x.c>x.o and x.c>val+0.015*atr and x.c>=p.c+0.015*atr):return 0
    else:
        if max(z.h for z in pull)<val-0.08*atr:return 0
        if not(x.c<x.o and x.c<val-0.015*atr and x.c<=p.c-0.015*atr):return 0
    recent=b[max(0,i-36):i]
    if max(z.h for z in recent)-min(z.l for z in recent)<360:return 0
    return d

def compound_sl_usd(lot):
    return round(max(0.01,lot-LOT_STEP),2)*TP

def sl_distance(lot,c,recovery):
    return c.recovery_sl if recovery else compound_sl_usd(lot)/lot

def entry_geometry_ok(sig_i,entry,d,b,c,I,lot,recovery):
    _,val,atr=v30.authority(sig_i,b,I)
    if atr<=0:return False,'FOMO'
    if abs(entry-val)/atr>c.entry_dist:return False,'FOMO'
    if abs(entry-b[sig_i].c)/atr>0.16:return False,'FOMO'
    sd=sl_distance(lot,c,recovery); actual_stop=entry-d*sd
    hist=b[max(0,sig_i-9):sig_i]
    if len(hist)<4:return False,'STOP'
    buffer=c.buffer_atr*atr
    if d>0:
        swing=min(z.l for z in hist); protected=swing-buffer
        if actual_stop>protected:return False,'STOP'
        if (entry-swing)/atr>1.75:return False,'FOMO'
    else:
        swing=max(z.h for z in hist); protected=swing+buffer
        if actual_stop<protected:return False,'STOP'
        if (swing-entry)/atr>1.75:return False,'FOMO'
    return True,'OK'

def run(b,start,c,I):
    bal=peak=min_bal=BASE_BAL; dd=0.0; lot=BASE_LOT; max_lot=lot
    tp_count=sl_count=recovery_entries=recovery_tps=trades=0
    reject_fomo=reject_stop=0; pos=None; st=b[start].ts; when=b[start].dt
    repair_active=False; repair_tp=0
    for i in range(max(start,WARM+3),len(b)):
        z=b[i]; recovery=bal<BASE_BAL-1e-9
        if recovery:
            lot=RECOVERY_LOT; repair_active=False; repair_tp=0
        elif lot<BASE_LOT-1e-9:
            lot=BASE_LOT; repair_active=False; repair_tp=0
        if pos is None:
            sig_i=i-1; d=signal(sig_i,b,c,I,lot,recovery)
            if not d:continue
            entry=z.o
            ok,why=entry_geometry_ok(sig_i,entry,d,b,c,I,lot,recovery)
            if not ok:
                if why=='STOP':reject_stop+=1
                else:reject_fomo+=1
                continue
            tp_dist=c.recovery_tp if recovery else TP
            sd=sl_distance(lot,c,recovery)
            pos=(d,entry,lot,tp_dist,sd,recovery); trades+=1
            if recovery:recovery_entries+=1
        d,en,L,tp_dist,sd,opened_recovery=pos
        stop=en-d*sd; target=en+d*tp_dist
        sl_hit=z.l<=stop if d>0 else z.h>=stop
        tp_hit=z.h>=target if d>0 else z.l<=target
        if sl_hit:
            bal-=L*sd; min_bal=min(min_bal,bal); sl_count+=1; when=z.dt; pos=None
            dd=max(dd,(peak-bal)/peak if peak>0 else 1.0)
            if bal<=0:
                return R(False,True,'BUST',bal,min_bal,max_lot,L,tp_count,sl_count,recovery_entries,recovery_tps,trades,reject_fomo,reject_stop,dd*100,(z.ts-st)/86400,z.dt)
            if bal<BASE_BAL-1e-9:
                lot=RECOVERY_LOT; repair_active=False; repair_tp=0; continue
            if repair_active:
                lot=round(max(BASE_LOT,L-LOT_STEP),2); repair_active=False; repair_tp=0
            else:
                lot=L; repair_active=True; repair_tp=0
            continue
        if tp_hit:
            bal+=L*tp_dist; peak=max(peak,bal); tp_count+=1; when=z.dt; pos=None
            if opened_recovery:
                recovery_tps+=1
                if bal>=BASE_BAL-1e-9:
                    lot=BASE_LOT; repair_active=False; repair_tp=0
                else:lot=RECOVERY_LOT
                continue
            if L>=MILESTONE-1e-9:
                return R(True,False,'PASS_1LOT',bal,min_bal,max(max_lot,L),L,tp_count,sl_count,recovery_entries,recovery_tps,trades,reject_fomo,reject_stop,dd*100,(z.ts-st)/86400,z.dt)
            if repair_active:
                if repair_tp==0:
                    repair_tp=1; lot=L
                else:
                    lot=round(L+LOT_STEP,2); repair_active=False; repair_tp=0
            else:lot=round(L+LOT_STEP,2)
            max_lot=max(max_lot,lot); continue
        adverse=max(0.0,en-z.l) if d>0 else max(0.0,z.h-en)
        floating=bal-adverse*L
        dd=max(dd,(peak-floating)/peak if peak>0 else 1.0)
        if floating<=0:
            return R(False,True,'BUST_FLOATING',bal,min_bal,max_lot,L,tp_count,sl_count,recovery_entries,recovery_tps,trades,reject_fomo,reject_stop,dd*100,(z.ts-st)/86400,z.dt)
    return R(False,False,'DATA_END',bal,min_bal,max_lot,lot,tp_count,sl_count,recovery_entries,recovery_tps,trades,reject_fomo,reject_stop,dd*100,(b[-1].ts-st)/86400,when)

def rank(rs):
    passes=sum(r.done for r in rs); busts=sum(r.bust for r in rs)
    worst_lot=min(r.max_lot for r in rs); med_lot=statistics.median(r.max_lot for r in rs)
    med_bal=statistics.median(r.balance for r in rs); worst_bal=min(r.min_balance for r in rs)
    tp_sum=sum(r.tp_count for r in rs); med_dd=statistics.median(r.dd for r in rs)
    return (passes,-busts,worst_lot,med_lot,med_bal,worst_bal,tp_sum,-med_dd)

def main():
    b=data.load(); I=v21.prep(b); cal=v30.calibration_starts(b); candidates=list(cfgs())
    print('=== BTC V34b ANTI-FOMO + STRUCTURE-PROTECTED EXACT-MONEY SL ===',flush=True)
    print('LOCKED TP300 exactPrevTP_SL firstSLretry firstTPrepair secondTPadvance secondSLstepDown below20=0.01 noCooldown stopAfter1.00LotTP',flush=True)
    print('ENTRY pullback/reclaim; no indicator-cross chase; fixed-money stop must already be beyond local swing + ATR buffer or skip',flush=True)
    print(f'CAL_CONFIGS {len(candidates)}',flush=True)
    best=None
    for n,c in enumerate(candidates,1):
        rs=[run(b,s,c,I) for s in cal]; rk=rank(rs)
        if best is None or rk>best[0]:best=(rk,c,rs)
        if n%8==0 or n==len(candidates):print(f'CAL_PROGRESS {n}/{len(candidates)} best={best[0]} cfg={best[1]}',flush=True)
    rk,c,_=best; print('BEST_CFG',c,'CAL_RANK',rk,flush=True)
    starts=v30.fresh_starts(b); rs=[run(b,s,c,I) for s in starts]
    for j,(s,r) in enumerate(zip(starts,rs),1):
        print(f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} maxLot={r.max_lot:.2f} currentLot={r.current_lot:.2f} balance={r.balance:.2f} minBal={r.min_balance:.2f} TP={r.tp_count} SL={r.sl_count} recoveryEntries={r.recovery_entries} recoveryTP={r.recovery_tps} trades={r.trades} rejectFOMO={r.reject_fomo} rejectStop={r.reject_stop} DD={r.dd:.2f}% days={r.days:.2f} end={r.when}',flush=True)
    summary=(f'BTC_FINAL PASS_1LOT={sum(r.done for r in rs)}/10 BUST={sum(r.bust for r in rs)}/10 DATA_END={sum(r.reason=="DATA_END" for r in rs)}/10 '
             f'MED_MAX_LOT={statistics.median(r.max_lot for r in rs):.2f} MAX_LOT={max(r.max_lot for r in rs):.2f} MIN_MAX_LOT={min(r.max_lot for r in rs):.2f} '
             f'TP_SUM={sum(r.tp_count for r in rs)} SL_SUM={sum(r.sl_count for r in rs)} MED_FINAL_BAL={statistics.median(r.balance for r in rs):.2f} '
             f'REJECT_FOMO={sum(r.reject_fomo for r in rs)} REJECT_STOP={sum(r.reject_stop for r in rs)} BEST_CFG={c}')
    print(summary,flush=True)

if __name__=='__main__':main()
