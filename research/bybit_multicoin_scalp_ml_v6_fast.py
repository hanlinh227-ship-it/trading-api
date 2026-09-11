#!/usr/bin/env python3
"""Performance wrapper for V6. Same model, labels, gates and outcomes.
Only prediction evaluation is vectorized so threshold scans do not call
predict_proba one candle at a time or recompute identical probabilities.
"""
from __future__ import annotations
import numpy as np
import bybit_multicoin_scalp_ml_v6 as m


def fast_evaluate(model,X,b,I,lo,hi,side,rr,threshold,cost_mult=1.0,delay=0,probs=None):
    e=m.Eval();eq=peak=0.;i=max(60,lo)
    base_lo=max(60,lo)
    if probs is None:
        probs=model.predict_proba(X[base_lo:hi+1])[:,1]
    while i<min(hi,len(b)-m.HOLD-3):
        p=float(probs[i-base_lo])
        if p<threshold:
            i+=1;continue
        o=m.outcome(i,b,I,side,rr,cost_mult,delay)
        if o is None:
            i+=1;continue
        last,kind,gross,net,cost=o
        if last>hi:break
        e.trades+=1;e.gross_r+=gross;e.net_r+=net;e.cost_r+=cost
        if kind=='TP':e.wins+=1
        else:
            e.losses+=1
            if kind=='TIMEOUT':e.timeouts+=1
        eq+=net;peak=max(peak,eq);e.max_dd_r=max(e.max_dd_r,peak-eq)
        i=last+1
    return e


def fast_choose_threshold(model,X,b,I,si,side,rr):
    lo,hi=si;base_lo=max(60,lo)
    probs=model.predict_proba(X[base_lo:hi+1])[:,1]
    best=None
    for th in np.arange(.50,.951,.01):
        e=fast_evaluate(model,X,b,I,lo,hi,side,rr,float(th),probs=probs)
        enough=e.trades>=m.MIN_SHADOW
        score=(1 if enough else 0,1 if enough and e.exp>0 else 0,e.wr,e.exp,-e.max_dd_r,e.trades)
        if best is None or score>best[0]:best=(score,float(th),e)
    return best

# Monkey-patch module globals used by calibrate. Semantics unchanged.
m.evaluate=fast_evaluate
m.choose_threshold=fast_choose_threshold

if __name__=='__main__':
    m.main()
