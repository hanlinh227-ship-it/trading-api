#!/usr/bin/env python3
"""Validate the first V3-completing XAU configuration from 10 deterministic alternate starts.
No SL/cut/timeout. $20 start, TP 3.00 price, 0.02 -> 1.00, +0.01 only after TP.
The config is selected once on the full 6-month V3 sample, then frozen for all 10 starts.
"""
from mt5_progressive_tp_backtest_v3 import load,DATA,cfgs,run,rank
bars=load(DATA['XAUUSD']['url'])
best=None; fixed=None
for n,c in enumerate(cfgs(),1):
 r=run('XAUUSD',bars,c)
 if best is None or rank(r)>rank(best): best=r
 if r.finished:
  fixed=c; print('FIXED_CONFIG',c,'selected_after',n); break
if fixed is None: raise SystemExit('No full-sample completing config')
N=len(bars); starts=[int((N*0.80)*k/10) for k in range(10)]
passed=0
for j,s in enumerate(starts,1):
 sub=bars[s:]; r=run('XAUUSD',sub,fixed); passed+=int(r.finished)
 print(f'RUN{j:02d} start={sub[0].dt} TP={r.tps}/99 finished={r.finished} bust={r.busted} equity=${r.equity:.2f} DD={r.maxdd:.2f}% lot={r.lot:.2f} end={r.when}')
print(f'SUMMARY pass={passed}/10 fixed={fixed}')
