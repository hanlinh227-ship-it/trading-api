#!/usr/bin/env python3
"""MultiCoin Scalp ML V6 — fixed RR research.

Purpose: materially change the alpha method after rule-family V5 failed.
The classifier predicts whether a full TP (1R or 2R) will be reached before
its fixed initial SL, using causal 5m OHLCV features only. A coin may promote
with LONG-only or SHORT-only if that is the robust edge; user target is per
coin, not forced directional symmetry.

Integrity:
- entry = next 5m open after a fully closed feature bar;
- TP/SL RR is exactly 1:1 or 1:2; initial stop is 1 ATR;
- same-candle TP+SL ambiguity => SL first;
- timeout never counts as a win;
- model trains on DEV; probability threshold/RR/direction selected on SHADOW;
- FINAL is untouched until the profile is frozen;
- >=220 FINAL trades and >=45 trades in each 45d FINAL window;
- costs and stress tests included;
- OHLCV proxy only, not fake L2/taker-flow/liquidations/OI.
"""
from __future__ import annotations

import argparse, json, math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import bybit_multicoin_scalp_rr_v4 as v4
import bybit_multicoin_scalp_rr_v5 as v5

STOP_ATR = 1.0
HOLD = 30
RR_SET = (1, 2)
MIN_SHADOW = 150
MIN_FINAL = 220
MIN_WINDOW = 45
TARGET_WR = 0.80
WORST_WR = 0.70
COST_BPS = 13.0

@dataclass
class Eval:
    trades:int=0;wins:int=0;losses:int=0;timeouts:int=0
    net_r:float=0.;gross_r:float=0.;cost_r:float=0.;max_dd_r:float=0.
    @property
    def wr(self): return self.wins/self.trades if self.trades else 0.
    @property
    def exp(self): return self.net_r/self.trades if self.trades else 0.

def ed(e:Eval):
    return {"trades":e.trades,"wins":e.wins,"losses":e.losses,"timeouts":e.timeouts,
            "win_rate":round(e.wr,6),"gross_r":round(e.gross_r,6),"net_r":round(e.net_r,6),
            "costs_r":round(e.cost_r,6),"expectancy_r":round(e.exp,6),"max_dd_r":round(e.max_dd_r,6)}

def features(b, I):
    n=len(b); X=np.zeros((n,24),dtype=np.float32)
    c=np.asarray([z.c for z in b],dtype=np.float64)
    for i in range(60,n):
        a=max(I['atr'][i],1e-12); px=max(c[i],1e-12); x=b[i]
        def ret(k): return (c[i]-c[i-k])/a
        vs=I['vs'][i]; vr=x.v/vs if vs and math.isfinite(vs) and vs>0 else 1.
        m=I['mean20'][i]; sd=I['sd20'][i]
        z=(x.c-m)/sd if math.isfinite(m) and math.isfinite(sd) and sd>0 else 0.
        hi=I['hi20'][i];lo=I['lo20'][i]
        dhi=(hi-x.c)/a if math.isfinite(hi) else 0.; dlo=(x.c-lo)/a if math.isfinite(lo) else 0.
        rng=max(x.h-x.l,1e-12); body=(x.c-x.o)/a; loc=(x.c-x.l)/rng
        hour=(b[i].ts//3_600_000)%24; dow=(b[i].ts//86_400_000+4)%7
        atr_prev=max(I['atr'][i-24],1e-12)
        X[i]=[
            ret(1),ret(2),ret(3),ret(6),ret(12),ret(24),
            (I['e9'][i]-I['e21'][i])/a,(I['e21'][i]-I['e50'][i])/a,
            (I['e9'][i]-I['e9'][i-6])/a,(I['e21'][i]-I['e21'][i-12])/a,
            I['rsi'][i]/100., min(vr,5.)/5., body, rng/a, loc,
            z/4., max(-5.,min(5.,dhi))/5.,max(-5.,min(5.,dlo))/5.,
            I['eff'][i],I['mom3'][i]/4., a/px*100., a/atr_prev,
            math.sin(2*math.pi*hour/24.),math.cos(2*math.pi*dow/7.)]
    return X

def outcome(i,b,I,side,rr,cost_mult=1.0,delay=0):
    ei=i+1+delay
    if ei>=len(b)-1:return None
    entry=b[ei].o; a=max(I['atr'][i],1e-12); stopd=STOP_ATR*a
    if stopd/entry < .0005:return None
    stop=entry-side*stopd; tp=entry+side*rr*stopd; last=ei
    for j in range(ei,min(len(b),ei+HOLD+1)):
        z=b[j];last=j
        hs=z.l<=stop if side>0 else z.h>=stop
        if hs:
            gross=-1.; kind='SL';break
        ht=z.h>=tp if side>0 else z.l<=tp
        if ht:
            gross=float(rr);kind='TP';break
    else:
        gross=side*(b[last].c-entry)/stopd;kind='TIMEOUT'
    cost=(COST_BPS*cost_mult/10000.)*entry/stopd
    return last,kind,gross,gross-cost,cost

def labels_for_range(b,I,lo,hi,side,rr):
    y=[]; inds=[]
    for i in range(max(60,lo),min(hi,len(b)-HOLD-3)):
        o=outcome(i,b,I,side,rr)
        if o is None:continue
        inds.append(i);y.append(1 if o[1]=='TP' else 0)
    return np.asarray(inds,dtype=np.int32),np.asarray(y,dtype=np.int8)

def fit_model(X,b,I,di,side,rr):
    inds,y=labels_for_range(b,I,*di,side,rr)
    if len(inds)<5000 or y.sum()<200:
        return None
    model=HistGradientBoostingClassifier(
        learning_rate=.06,max_iter=180,max_leaf_nodes=23,max_depth=None,
        min_samples_leaf=90,l2_regularization=1.5,random_state=260905,
        early_stopping=True,validation_fraction=.15,n_iter_no_change=18)
    model.fit(X[inds],y)
    return model

def evaluate(model,X,b,I,lo,hi,side,rr,threshold,cost_mult=1.0,delay=0):
    e=Eval(); eq=peak=0.; i=max(60,lo)
    while i<min(hi,len(b)-HOLD-3):
        p=float(model.predict_proba(X[i:i+1])[0,1])
        if p<threshold:
            i+=1;continue
        o=outcome(i,b,I,side,rr,cost_mult,delay)
        if o is None:
            i+=1;continue
        last,kind,gross,net,cost=o
        # Never allow one trade to cross beyond the scored block.
        if last>hi:break
        e.trades+=1;e.gross_r+=gross;e.net_r+=net;e.cost_r+=cost
        if kind=='TP':e.wins+=1
        else:
            e.losses+=1
            if kind=='TIMEOUT':e.timeouts+=1
        eq+=net;peak=max(peak,eq);e.max_dd_r=max(e.max_dd_r,peak-eq)
        i=last+1
    return e

def choose_threshold(model,X,b,I,si,side,rr):
    best=None
    # A dense but deterministic threshold scan; only SHADOW is used here.
    for th in np.arange(.50,.951,.01):
        e=evaluate(model,X,b,I,*si,side,rr,float(th))
        enough=e.trades>=MIN_SHADOW
        score=(1 if enough else 0,1 if enough and e.exp>0 else 0,e.wr,e.exp,-e.max_dd_r,e.trades)
        if best is None or score>best[0]:best=(score,float(th),e)
    return best

def calibrate(sym,b,manifest):
    block=v4.split_block(b)
    if not block:return {'symbol':sym,'status':'DATA_GAP','reason':'no clean split','manifest':manifest}
    di,si,fw,shift=block;I=v4.prep(b);X=features(b,I)
    candidates=[]
    for side in (1,-1):
        for rr in RR_SET:
            model=fit_model(X,b,I,di,side,rr)
            if model is None:continue
            z=choose_threshold(model,X,b,I,si,side,rr)
            if z is None:continue
            score,th,shadow=z
            candidates.append((score,side,rr,th,shadow,model))
    if not candidates:return {'symbol':sym,'status':'NO_MODEL','reason':'no usable model','manifest':manifest}
    candidates.sort(key=lambda z:z[0],reverse=True)
    _,side,rr,th,shadow,model=candidates[0]
    # Profile is frozen here. FINAL is first consulted below.
    fs=[evaluate(model,X,b,I,*w,side,rr,th) for w in fw]
    agg=Eval()
    # Aggregate with a conservative max window drawdown.
    for e in fs:
        agg.trades+=e.trades;agg.wins+=e.wins;agg.losses+=e.losses;agg.timeouts+=e.timeouts
        agg.net_r+=e.net_r;agg.gross_r+=e.gross_r;agg.cost_r+=e.cost_r;agg.max_dd_r=max(agg.max_dd_r,e.max_dd_r)
    worst=min((e.wr for e in fs),default=0.)
    stress15=[evaluate(model,X,b,I,*w,side,rr,th,1.5) for w in fw]
    stress20=[evaluate(model,X,b,I,*w,side,rr,th,2.0) for w in fw]
    delay=[evaluate(model,X,b,I,*w,side,rr,th,1.0,1) for w in fw]
    def marg(xs):
        t=sum(x.trades for x in xs);nr=sum(x.net_r for x in xs)
        return nr/t if t else -999.
    robust=marg(stress15)>0 and marg(stress20)>0 and marg(delay)>0
    base=(agg.wr>=TARGET_WR and worst>=WORST_WR and agg.trades>=MIN_FINAL and
          all(x.trades>=MIN_WINDOW for x in fs) and agg.exp>0 and all(x.net_r>0 for x in fs))
    locked=base and robust
    reasons=[]
    if agg.wr<TARGET_WR:reasons.append('FINAL_WR_LT_80')
    if worst<WORST_WR:reasons.append('WORST_WINDOW_LT_70')
    if agg.trades<MIN_FINAL:reasons.append('FINAL_TRADES_LT_220')
    if any(x.trades<MIN_WINDOW for x in fs):reasons.append('WINDOW_TRADES_LT_45')
    if agg.exp<=0:reasons.append('NONPOSITIVE_EXPECTANCY')
    if any(x.net_r<=0 for x in fs):reasons.append('NEGATIVE_WINDOW_R')
    if not robust:reasons.append('STRESS_FAIL')
    return {
        'symbol':sym,'status':'LOCKED' if locked else 'RESEARCH','reason':'PASS' if locked else reasons,
        'profile_version':'scalp_ml_v6','manifest':manifest,'data_gap_shift_days':shift,
        'profile':{'direction':'LONG' if side>0 else 'SHORT','side':side,'rr':rr,'stop_atr':STOP_ATR,
                   'hold_bars':HOLD,'probability_threshold':round(th,4),'model':'HistGradientBoostingClassifier'},
        'shadow':ed(shadow),'final_windows':[{'range':[v4.iso(b[w[0]].ts),v4.iso(b[w[1]].ts)],**ed(e)} for w,e in zip(fw,fs)],
        'final_aggregate':ed(agg),'worst_final_window_wr':round(worst,6),
        'stress':{'cost_1_5x_expectancy':round(marg(stress15),6),'cost_2x_expectancy':round(marg(stress20),6),
                  'delay_1bar_expectancy':round(marg(delay),6),'pass':robust},
        'gate':{'target_wr':TARGET_WR,'min_final_trades':MIN_FINAL,'min_window_trades':MIN_WINDOW,'locked':locked},
        'limitations':['5m USD-M futures OHLCV proxy','No Bybit historical L2/taker-flow/liquidation/OI replay','Bybit forward/replay required before production']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbols',default=','.join(v4.UNIVERSE));ap.add_argument('--out',default='research/results/scalp_ml_v6.json');a=ap.parse_args()
    syms=[x.strip().upper() for x in a.symbols.split(',') if x.strip()];res=[]
    print('=== MULTICOIN SCALP ML V6 FIXED RR ===',flush=True)
    for n,sym in enumerate(syms,1):
        print(f'[{n}/{len(syms)}] {sym} load',flush=True)
        try:
            b,m=v5.load_futures_archive(sym);print(f"DATA {sym} bars={m['bars']} gaps={m['gaps']}",flush=True);r=calibrate(sym,b,m)
        except Exception as e:r={'symbol':sym,'status':'ERROR','reason':repr(e)}
        res.append(r)
        if r.get('final_aggregate'):
            x=r['final_aggregate'];p=r['profile'];print(f"RESULT {sym} {r['status']} WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_final_window_wr']:.2f}% {p['direction']} RR{p['rr']} TH={p['probability_threshold']:.2f} SHADOW_WR={100*r['shadow']['win_rate']:.2f}% reason={r['reason']}",flush=True)
        else:print('RESULT',sym,r['status'],r.get('reason'),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'engine':'MULTICOIN_SCALP_ML_V6','research_only':True,
             'universe':syms,'locked':[r['symbol'] for r in res if r.get('status')=='LOCKED'],
             'unresolved':[r['symbol'] for r in res if r.get('status')!='LOCKED'],'results':res}
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LOCKED',summary['locked'],flush=True);print('REPORT',out,flush=True)
if __name__=='__main__':main()
