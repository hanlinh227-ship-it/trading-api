#!/usr/bin/env python3
"""BTC V35 — balance-safe dynamic compound + anti-FOMO structure-protected SL.
Research only. No production/live changes.

Key fix from V34b: a compound lot may not be opened when its locked exact-money
SL is larger than the realizable balance reserve. The ladder still has NO fixed
maximum lot. If drawdown makes the current lot too large, step down by 0.01 until
the exact SL can be paid; as balance/TP recovers, the ladder can climb again.
"""
from __future__ import annotations
import itertools, statistics, sys
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import btc_binance_m5_full_loader as data
import btc_v30_complete_data_quality_entry_10x as v30
import dual_xau_btc_v21_vwap_unbounded as v21

BASE_BAL=20.; BASE_LOT=.02; REC_LOT=.01; STEP=.01; TP=300.; MILESTONE=1.; WARM=700

@dataclass(frozen=True)
class Cfg:
    base_score:float; high_score:float; close_dist:float; entry_dist:float
    buffer_atr:float; recovery_tp:float=180.; recovery_sl:float=90.
@dataclass
class R:
    done:bool;bust:bool;reason:str;balance:float;min_balance:float;max_lot:float;current_lot:float
    tp_count:int;sl_count:int;recovery_entries:int;recovery_tps:int;trades:int
    reject_fomo:int;reject_stop:int;balance_steps:int;dd:float;days:float;when:str

def cfgs():
    for base,high,cd,buf in itertools.product((5.0,5.4),(5.8,6.2),(.42,.52),(.06,.10)):
        yield Cfg(base,high,cd,min(.60,cd+.10),buf)

def threshold(lot,c,recovery):
    if recovery:return max(6.0,c.high_score)
    if lot<=.05+1e-9:return c.base_score
    if lot<=.20+1e-9:return max(5.4,c.base_score+.20)
    if lot<=.50+1e-9:return c.high_score
    return c.high_score+.20

def signal(i,b,c,I,lot,recovery):
    if i<WARM:return 0
    sc,val,atr=v30.authority(i,b,I)
    if abs(sc)<threshold(lot,c,recovery) or atr<65 or atr>650:return 0
    d=1 if sc>0 else -1;x,p=b[i],b[i-1];E,V=I['e'],I['v']
    if abs(x.c-val)/atr>c.close_dist:return 0
    if (x.h-x.l)/atr>1.08 or abs(x.c-x.o)/atr>.68:return 0
    if d>0:
        if not(E[8][i]>E[20][i]>E[36][i] and E[60][i]>E[150][i]):return 0
        if not(E[20][i]>E[20][i-8] and E[60][i]>E[60][i-20]):return 0
        if V[96][i]<=V[96][i-10]:return 0
    else:
        if not(E[8][i]<E[20][i]<E[36][i] and E[60][i]<E[150][i]):return 0
        if not(E[20][i]<E[20][i-8] and E[60][i]<E[60][i-20]):return 0
        if V[96][i]>=V[96][i-10]:return 0
    pull=b[i-4:i]
    if d>0:
        if min(z.l for z in pull)>val+.10*atr:return 0
        if not(x.c>x.o and x.c>val+.01*atr and x.c>=p.c):return 0
    else:
        if max(z.h for z in pull)<val-.10*atr:return 0
        if not(x.c<x.o and x.c<val-.01*atr and x.c<=p.c):return 0
    recent=b[max(0,i-36):i]
    if max(z.h for z in recent)-min(z.l for z in recent)<350:return 0
    return d

def compound_sl_usd(lot):return round(max(.01,lot-STEP),2)*TP
def sl_dist(lot,c,recovery):return c.recovery_sl if recovery else compound_sl_usd(lot)/lot

def normalize_lot(lot,bal):
    """No fixed max. Step down only when exact SL cannot be paid with $1 reserve."""
    steps=0
    while lot>BASE_LOT+1e-9 and compound_sl_usd(lot)>max(0.,bal-1.0):
        lot=round(lot-STEP,2);steps+=1
    return lot,steps

def geometry(sig_i,entry,d,b,c,I,lot,recovery):
    _,val,atr=v30.authority(sig_i,b,I)
    if atr<=0:return False,'FOMO'
    if abs(entry-val)/atr>c.entry_dist:return False,'FOMO'
    if abs(entry-b[sig_i].c)/atr>.18:return False,'FOMO'
    sd=sl_dist(lot,c,recovery);actual=entry-d*sd
    # Local liquidity swing: shorter 5-bar structure avoids rejecting valid deep pullbacks
    # while still forcing the exact-money stop outside the immediate sweep zone.
    hist=b[max(0,sig_i-6):sig_i]
    if len(hist)<4:return False,'STOP'
    buffer=max(12.,c.buffer_atr*atr)
    if d>0:
        protected=min(z.l for z in hist)-buffer
        if actual>protected:return False,'STOP'
    else:
        protected=max(z.h for z in hist)+buffer
        if actual<protected:return False,'STOP'
    return True,'OK'

def run(b,start,c,I):
    bal=peak=minbal=BASE_BAL;dd=0.;lot=BASE_LOT;maxlot=lot;pos=None
    tp=sl=rent=rtp=tr=rf=rs=bstep=0;repair=False;repair_tp=0;st=b[start].ts;when=b[start].dt
    for i in range(max(start,WARM+4),len(b)):
        z=b[i];recovery=bal<BASE_BAL-1e-9
        if recovery:
            lot=REC_LOT;repair=False;repair_tp=0
        else:
            if lot<BASE_LOT-1e-9:lot=BASE_LOT;repair=False;repair_tp=0
            nl,n=normalize_lot(lot,bal)
            if n:
                lot=nl;bstep+=n;repair=False;repair_tp=0
        if pos is None:
            sig=i-1;d=signal(sig,b,c,I,lot,recovery)
            if not d:continue
            entry=z.o;ok,why=geometry(sig,entry,d,b,c,I,lot,recovery)
            if not ok:
                if why=='STOP':rs+=1
                else:rf+=1
                continue
            tpd=c.recovery_tp if recovery else TP;sd=sl_dist(lot,c,recovery)
            pos=(d,entry,lot,tpd,sd,recovery);tr+=1
            if recovery:rent+=1
        d,en,L,tpd,sd,opened_rec=pos;stop=en-d*sd;target=en+d*tpd
        sh=z.l<=stop if d>0 else z.h>=stop;th=z.h>=target if d>0 else z.l<=target
        if sh:
            bal-=L*sd;minbal=min(minbal,bal);sl+=1;when=z.dt;pos=None;dd=max(dd,(peak-bal)/peak)
            if bal<=0:return R(False,True,'BUST',bal,minbal,maxlot,L,tp,sl,rent,rtp,tr,rf,rs,bstep,dd*100,(z.ts-st)/86400,z.dt)
            if bal<BASE_BAL-1e-9:
                lot=REC_LOT;repair=False;repair_tp=0;continue
            if repair:
                lot=round(max(BASE_LOT,L-STEP),2);repair=False;repair_tp=0
            else:
                lot=L;repair=True;repair_tp=0
            continue
        if th:
            bal+=L*tpd;peak=max(peak,bal);tp+=1;when=z.dt;pos=None
            if opened_rec:
                rtp+=1
                if bal>=BASE_BAL-1e-9:lot=BASE_LOT;repair=False;repair_tp=0
                else:lot=REC_LOT
                continue
            if L>=MILESTONE-1e-9:return R(True,False,'PASS_1LOT',bal,minbal,max(maxlot,L),L,tp,sl,rent,rtp,tr,rf,rs,bstep,dd*100,(z.ts-st)/86400,z.dt)
            if repair:
                if repair_tp==0:repair_tp=1;lot=L
                else:lot=round(L+STEP,2);repair=False;repair_tp=0
            else:lot=round(L+STEP,2)
            maxlot=max(maxlot,lot);continue
        adverse=max(0.,en-z.l) if d>0 else max(0.,z.h-en);floating=bal-adverse*L
        dd=max(dd,(peak-floating)/peak)
        if floating<=0:return R(False,True,'BUST_FLOATING',bal,minbal,maxlot,L,tp,sl,rent,rtp,tr,rf,rs,bstep,dd*100,(z.ts-st)/86400,z.dt)
    return R(False,False,'DATA_END',bal,minbal,maxlot,lot,tp,sl,rent,rtp,tr,rf,rs,bstep,dd*100,(b[-1].ts-st)/86400,when)

def rank(a):
    return (sum(x.done for x in a),-sum(x.bust for x in a),min(x.max_lot for x in a),statistics.median(x.max_lot for x in a),statistics.median(x.balance for x in a),min(x.min_balance for x in a),sum(x.tp_count for x in a),-statistics.median(x.dd for x in a))

def main():
    b=data.load();I=v21.prep(b);cal=v30.calibration_starts(b);cs=list(cfgs())
    print('=== BTC V35 BALANCE-SAFE ANTI-FOMO STRUCTURE SL ===',flush=True)
    print('TP300 exactPrevTP_SL noFixedMaxLot balanceFeasibility stepDown firstSLretry firstTPrepair secondTPadvance below20=0.01 noCooldown',flush=True)
    print(f'CAL_CONFIGS {len(cs)}',flush=True);best=None
    for n,c in enumerate(cs,1):
        a=[run(b,s,c,I) for s in cal];rk=rank(a)
        if best is None or rk>best[0]:best=(rk,c,a)
        if n%4==0 or n==len(cs):print(f'CAL_PROGRESS {n}/{len(cs)} best={best[0]} cfg={best[1]}',flush=True)
    rk,c,_=best;print('BEST_CFG',c,'CAL_RANK',rk,flush=True)
    starts=v30.fresh_starts(b);a=[run(b,s,c,I) for s in starts]
    for j,(s,r) in enumerate(zip(starts,a),1):
        print(f'BTC_TEST{j:02d} start={b[s].dt} status={r.reason} maxLot={r.max_lot:.2f} currentLot={r.current_lot:.2f} balance={r.balance:.2f} minBal={r.min_balance:.2f} TP={r.tp_count} SL={r.sl_count} trades={r.trades} rejectFOMO={r.reject_fomo} rejectStop={r.reject_stop} balanceSteps={r.balance_steps} DD={r.dd:.2f}% days={r.days:.2f} end={r.when}',flush=True)
    print(f'BTC_FINAL PASS_1LOT={sum(r.done for r in a)}/10 BUST={sum(r.bust for r in a)}/10 DATA_END={sum(r.reason=="DATA_END" for r in a)}/10 MED_MAX_LOT={statistics.median(r.max_lot for r in a):.2f} MAX_LOT={max(r.max_lot for r in a):.2f} MIN_MAX_LOT={min(r.max_lot for r in a):.2f} TP_SUM={sum(r.tp_count for r in a)} SL_SUM={sum(r.sl_count for r in a)} MED_FINAL_BAL={statistics.median(r.balance for r in a):.2f} REJECT_FOMO={sum(r.reject_fomo for r in a)} REJECT_STOP={sum(r.reject_stop for r in a)} BALANCE_STEPS={sum(r.balance_steps for r in a)} BEST_CFG={c}',flush=True)
if __name__=='__main__':main()
