#!/usr/bin/env python3
"""Random-window refinement harness for XAUUSD and BTCUSD.
Rules: $20 start, one position, no SL/cut/timeout, XAU TP 3 price, BTC TP 300 price,
lot 0.02->1.00 +0.01 only after TP, 1 M5 cooldown. Ten deterministic-random starts per round.
This harness evaluates candidate configs on the same frozen 10 starts per symbol, then reports pass count.
"""
from __future__ import annotations
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mt5_progressive_tp_backtest_v3 import load,DATA,cfgs,run
from mt5_progressive_tp_backtest_v8 import load as load_btc, prep as prep_btc, run as run_btc, cfgs as cfgs_btc

SEED=20260829

def frozen_starts(n:int, count=10):
    rnd=random.Random(SEED)
    hi=max(1,int(n*0.78))
    return sorted(rnd.sample(range(0,hi),count))

def eval_xau(bars, starts, c):
    return [run('XAUUSD',bars[s:],c) for s in starts]

def score_xau(rs):
    return (sum(r.finished for r in rs), sum(r.tps for r in rs), -sum(r.maxdd for r in rs), -sum(r.maxhold for r in rs))

def main():
    print('=== DUAL RANDOM10 REFINE V10 ===')
    xb=load(DATA['XAUUSD']['url']); xs=frozen_starts(len(xb))
    print('XAU starts:', [xb[s].dt for s in xs])
    best=None;bestc=None;tested=0
    for c in cfgs():
        tested+=1;rs=eval_xau(xb,xs,c);sc=score_xau(rs)
        if best is None or sc>best:best=sc;bestc=(c,rs)
        if sc[0]==10:break
    c,rs=bestc
    print('XAU_BEST',c,'tested',tested,'pass',best[0],'/10','sumTP',best[1])
    for i,(s,r) in enumerate(zip(xs,rs),1):
        print(f'XAU{i:02d} start={xb[s].dt} TP={r.tps}/99 done={r.finished} bust={r.busted} DD={r.maxdd:.2f}% lot={r.lot:.2f} end={r.when}')

    bb=load_btc(); bs=frozen_starts(len(bb))
    print('BTC starts:', [bb[s].dt for s in bs])
    best=None;bestc=None;tested=0
    for c in cfgs_btc():
        tested+=1;rs=[]
        for s in bs:
            sub=bb[s:];Ii=prep_btc(sub);rs.append(run_btc(sub,c,Ii))
        sc=(sum(r.done for r in rs),sum(r.tps for r in rs),-sum(r.dd for r in rs),-sum(r.hold for r in rs))
        if best is None or sc>best:best=sc;bestc=(c,rs)
        if sc[0]==10:break
    c,rs=bestc
    print('BTC_BEST',c,'tested',tested,'pass',best[0],'/10','sumTP',best[1])
    for i,(s,r) in enumerate(zip(bs,rs),1):
        print(f'BTC{i:02d} start={bb[s].dt} TP={r.tps}/99 done={r.done} bust={r.bust} DD={r.dd:.2f}% lot={r.lot:.2f} end={r.when}')

if __name__=='__main__':main()
