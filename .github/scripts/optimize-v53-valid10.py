#!/usr/bin/env python3
import json, random, runpy
from copy import deepcopy
from datetime import datetime, timezone

M=runpy.run_path('.github/scripts/optimize-v52-scalp-10round.py',run_name='v53_lib')
# Keep $1 NET floor and <=2.25% risk, but make hard-stop geometry economically feasible.
BASE=deepcopy(M['BASE'])
BASE.update({
 'ema_fast':14,'ema_slow':55,'trend_slope_bars':6,'trend_slope_atr':0.16,
 'pullback_atr':0.14,'reaccel_body_atr':0.13,'reaccel_vol':1.30,
 'sweep_lookback':30,'sweep_reclaim_atr':0.08,'sweep_vol':1.45,
 'breakout_enabled':False,'rr_trend':0.90,'rr_sweep':0.85,'rr_breakout':0.95,
 'stop_min_pct':0.0045,'stop_max_pct':0.0090,'max_hold':6,'cooldown':3,
 'risk_pct':2.25,'body_filter_atr':0.11
})
R=random.Random(5302026)
BOUNDS={
 'ema_fast':(8,24),'ema_slow':(40,100),'trend_slope_bars':(3,12),'trend_slope_atr':(.08,.40),
 'pullback_atr':(.05,.30),'reaccel_body_atr':(.08,.32),'reaccel_vol':(1.0,2.4),
 'sweep_lookback':(18,60),'sweep_reclaim_atr':(.03,.20),'sweep_vol':(1.0,2.8),
 'rr_trend':(.82,1.35),'rr_sweep':(.80,1.30),'rr_breakout':(.85,1.35),
 'stop_min_pct':(.0038,.0070),'stop_max_pct':(.0060,.0120),'max_hold':(3,8),'cooldown':(1,8),
 'body_filter_atr':(.06,.30)
}
INTS={'ema_fast','ema_slow','trend_slope_bars','sweep_lookback','max_hold','cooldown'}

def mutate(p,roundn):
    q=deepcopy(p); scale=max(.25,1-roundn*.065)
    for _ in range(R.randint(4,8)):
        k=R.choice(list(BOUNDS)); lo,hi=BOUNDS[k]
        if k in INTS:
            step=max(1,int((hi-lo)*.16*scale));q[k]=int(max(lo,min(hi,q[k]+R.randint(-step,step))))
        else:
            step=(hi-lo)*.18*scale;q[k]=max(lo,min(hi,q[k]+R.uniform(-step,step)))
    # Breakout stays disabled until price-only proxy proves the two precision lanes first.
    q['breakout_enabled']=False;q['risk_pct']=2.25
    if q['ema_fast']>=q['ema_slow']-8:q['ema_fast']=max(8,q['ema_slow']-10)
    if q['stop_min_pct']>q['stop_max_pct']-.001:q['stop_min_pct']=max(.0038,q['stop_max_pct']-.0015)
    return q

def train_score(z):
    n=z['trades']
    if n<12:return -5000+n*10
    s=z['winRate']*180+min(z['pf'],3)*28+max(-2,min(2,z['expectancy']))*20-z['maxDD']*1.3
    if n<25:s-=35
    if z['pf']<1:s-=70
    if z['expectancy']<=0:s-=60
    return s

def val_score(z):
    n=z['trades']
    if n<12:return -5000+n*10
    return z['winRate']*180+min(z['pf'],3)*25+max(-2,min(2,z['expectancy']))*15-z['maxDD']

def main():
    data={s:M['fetch'](s) for s in M['SYMBOLS']}
    current=deepcopy(BASE); rounds=[]; best=None;bestp=None;stopped=False
    for r in range(1,11):
        candidates=[deepcopy(current)]+[mutate(current,r) for _ in range(18)]
        ranked=[]
        for p in candidates:
            tr=M['eval_params'](data,p,'train');ranked.append((train_score(tr),p,tr))
        ranked.sort(key=lambda x:x[0],reverse=True);_,current,tr=ranked[0]
        va=M['eval_params'](data,current,'val')
        rounds.append({'round':r,'params':deepcopy(current),'train':tr,'validation':va})
        print('ROUND',r,'TRAIN',json.dumps(tr),'VAL',json.dumps(va),'PARAMS',json.dumps(current,separators=(',',':')),flush=True)
        if best is None or val_score(va)>val_score(best):best=deepcopy(va);bestp=deepcopy(current)
        if va['trades']>=20 and va['winRate']>.80 and va['pf']>=1.20 and va['expectancy']>0 and va['maxDD']<=12:
            stopped=True;print('STOP_OVER_80_VALIDATED',r,flush=True);break
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V53_10_ROUND_ECONOMICALLY_FEASIBLE_PRECISION_SCALP','source':'BINANCE_PUBLIC_SPOT_1M_PROXY','symbols':M['SYMBOLS'],'costRate':M['ROUNDTRIP_COST_RATE'],'minPlannedNetUsd':M['MIN_PLANNED_NET_USD'],'riskPctMax':2.25,'rounds':rounds,'bestValidation':best,'bestParams':bestp,'stoppedOver80':stopped,'criteria':{'minValidationTrades':20,'winRateGreaterThan':.80,'pfMin':1.20,'expectancyPositive':True,'maxDDPct':12},'note':'1m OHLCV proxy; not full Bybit order-book/trade-flow replay'}
    with open('v53-valid10-report.json','w') as f:json.dump(report,f,indent=2)
    print('FINAL_REPORT='+json.dumps(report,separators=(',',':')),flush=True)
if __name__=='__main__':main()
