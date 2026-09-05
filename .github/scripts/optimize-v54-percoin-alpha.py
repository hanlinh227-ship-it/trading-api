#!/usr/bin/env python3
import json, math, os, random, statistics, time, urllib.parse, urllib.request
from copy import deepcopy
from datetime import datetime, timezone

SYMBOL=os.environ.get('SYMBOL','BTCUSDT').upper()
DAYS=int(os.environ.get('DAYS','18'))
TRAIN_DAYS=int(os.environ.get('TRAIN_DAYS','10'))
VAL_DAYS=int(os.environ.get('VAL_DAYS','4'))
TEST_DAYS=DAYS-TRAIN_DAYS-VAL_DAYS
MAX_GENERATIONS=int(os.environ.get('MAX_GENERATIONS','24'))
CANDIDATES_PER_GEN=int(os.environ.get('CANDIDATES_PER_GEN','14'))
ROUNDTRIP_COST_RATE=0.00130
TARGET_WR=0.80
MIN_VAL_TRADES=18
MIN_TEST_TRADES=18
R=random.Random(5402026 + sum(map(ord,SYMBOL)))

# Asset-normalized features only: suitable for transfer to other crypto/futures/TradFi.
BASE={
 'family':'SWEEP_TREND',
 'ema_fast':16,'ema_slow':55,'atr_n':14,'vol_n':20,
 'trend_slope_bars':7,'trend_slope_atr':0.16,
 'pullback_atr':0.10,'reaccel_body_atr':0.12,'reaccel_vol':1.65,
 'sweep_lookback':32,'sweep_depth_atr':0.04,'reclaim_atr':0.08,'sweep_vol':1.55,
 'confirm_body_atr':0.10,'confirm_close_loc':0.62,
 'wick_ratio':1.15,'range_expansion':1.10,
 'stop_min_pct':0.0048,'stop_max_pct':0.0115,
 'rr':0.80,'max_hold':4,'cooldown':4
}

BOUNDS={
 'ema_fast':(8,28),'ema_slow':(35,110),'trend_slope_bars':(3,14),'trend_slope_atr':(.05,.45),
 'pullback_atr':(.02,.30),'reaccel_body_atr':(.05,.50),'reaccel_vol':(.8,3.2),
 'sweep_lookback':(12,72),'sweep_depth_atr':(.0,.25),'reclaim_atr':(.01,.30),'sweep_vol':(.8,3.5),
 'confirm_body_atr':(.03,.50),'confirm_close_loc':(.52,.92),'wick_ratio':(.6,3.5),'range_expansion':(.7,2.5),
 'stop_min_pct':(.0035,.0100),'stop_max_pct':(.0060,.0180),'rr':(.55,1.15),'max_hold':(2,7),'cooldown':(1,10)
}
INTS={'ema_fast','ema_slow','trend_slope_bars','sweep_lookback','max_hold','cooldown'}
FAMILIES=['SWEEP_ONLY','TREND_ONLY','SWEEP_TREND']


def get_json(url,retries=5):
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v54-percoin-alpha'})
            with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode())
        except Exception:
            if i==retries-1:raise
            time.sleep(1.0+i)


def fetch(symbol):
    end=int(time.time()*1000); start=end-DAYS*86400000; cur=start; out=[]
    while cur<end:
        q=urllib.parse.urlencode({'symbol':symbol,'interval':'1m','startTime':cur,'endTime':end,'limit':1000})
        rows=get_json('https://data-api.binance.vision/api/v3/klines?'+q)
        if not rows:break
        for x in rows:
            out.append({'t':int(x[0]),'o':float(x[1]),'h':float(x[2]),'l':float(x[3]),'c':float(x[4]),'v':float(x[5])})
        nxt=int(rows[-1][0])+60000
        if nxt<=cur:break
        cur=nxt
        if len(rows)<1000:break
        time.sleep(.02)
    d={x['t']:x for x in out}
    return [d[k] for k in sorted(d)]


def ema(vals,n):
    a=2/(n+1); e=None; out=[]
    for x in vals:
        e=x if e is None else a*x+(1-a)*e; out.append(e)
    return out


def atr(rows,n=14):
    tr=[]
    for i,r in enumerate(rows):
        pc=rows[i-1]['c'] if i else r['c']
        tr.append(max(r['h']-r['l'],abs(r['h']-pc),abs(r['l']-pc)))
    return ema(tr,n)


def rollmean(vals,n):
    out=[None]*len(vals); s=0.0
    for i,x in enumerate(vals):
        s+=x
        if i>=n:s-=vals[i-n]
        if i>=n-1:out[i]=s/n
    return out


def extreme(rows,i,n,side):
    if i<n:return None
    xs=rows[i-n:i]
    return max(x['h'] for x in xs) if side=='high' else min(x['l'] for x in xs)


def close_loc(r):
    rg=max(r['h']-r['l'],1e-12)
    return (r['c']-r['l'])/rg


def wick_metrics(r):
    body=max(abs(r['c']-r['o']),1e-12)
    upper=r['h']-max(r['o'],r['c']); lower=min(r['o'],r['c'])-r['l']
    return upper/body,lower/body


def prep(rows,p):
    c=[x['c'] for x in rows]; v=[x['v'] for x in rows]
    return ema(c,p['ema_fast']),ema(c,p['ema_slow']),atr(rows,p['atr_n']),rollmean(v,p['vol_n'])


def candidate_signal(rows,i,p,ef,es,aa,vv):
    # Signal at bar i, confirmation at i+1, entry at i+2. This removes look-ahead and avoids first-tick chasing.
    if i<max(120,p['ema_slow']+20,p['sweep_lookback']+5) or i+2>=len(rows) or not vv[i] or aa[i]<=0:return None
    r=rows[i]; prev=rows[i-1]; conf=rows[i+1]; a=aa[i]
    volr=r['v']/max(vv[i],1e-12); rg=(r['h']-r['l'])/a
    ub,lb=wick_metrics(r); hi=extreme(rows,i,p['sweep_lookback'],'high'); lo=extreme(rows,i,p['sweep_lookback'],'low')
    fam=p['family']

    if fam in ('SWEEP_ONLY','SWEEP_TREND') and hi is not None:
        # Long: sweep prior low, close back inside, lower rejection wick, then a second bullish confirmation bar.
        if (r['l'] < lo-p['sweep_depth_atr']*a and r['c'] > lo+p['reclaim_atr']*a and lb>=p['wick_ratio'] and
            volr>=p['sweep_vol'] and rg>=p['range_expansion'] and conf['c']>r['c'] and conf['c']>conf['o'] and
            (conf['c']-conf['o'])/a>=p['confirm_body_atr'] and close_loc(conf)>=p['confirm_close_loc']):
            return ('SWEEP_RECLAIM_2STEP','Buy',r['l'])
        if (r['h'] > hi+p['sweep_depth_atr']*a and r['c'] < hi-p['reclaim_atr']*a and ub>=p['wick_ratio'] and
            volr>=p['sweep_vol'] and rg>=p['range_expansion'] and conf['c']<r['c'] and conf['c']<conf['o'] and
            (conf['o']-conf['c'])/a>=p['confirm_body_atr'] and close_loc(conf)<=1-p['confirm_close_loc']):
            return ('SWEEP_RECLAIM_2STEP','Sell',r['h'])

    if fam in ('TREND_ONLY','SWEEP_TREND'):
        sb=p['trend_slope_bars']
        if i>sb:
            up=ef[i]>es[i] and (ef[i]-ef[i-sb])/a>=p['trend_slope_atr']
            dn=ef[i]<es[i] and (ef[i-sb]-ef[i])/a>=p['trend_slope_atr']
            recent=rows[i-3:i+1]
            if up:
                touched=any(x['l']<=ef[i]+p['pullback_atr']*a for x in recent)
                if (touched and r['c']>prev['h'] and r['c']>r['o'] and (r['c']-r['o'])/a>=p['reaccel_body_atr'] and
                    volr>=p['reaccel_vol'] and conf['c']>r['c'] and conf['c']>conf['o'] and close_loc(conf)>=p['confirm_close_loc']):
                    anchor=min(x['l'] for x in recent)
                    return ('TREND_REACCEL_2STEP','Buy',anchor)
            if dn:
                touched=any(x['h']>=ef[i]-p['pullback_atr']*a for x in recent)
                if (touched and r['c']<prev['l'] and r['c']<r['o'] and (r['o']-r['c'])/a>=p['reaccel_body_atr'] and
                    volr>=p['reaccel_vol'] and conf['c']<r['c'] and conf['c']<conf['o'] and close_loc(conf)<=1-p['confirm_close_loc']):
                    anchor=max(x['h'] for x in recent)
                    return ('TREND_REACCEL_2STEP','Sell',anchor)
    return None


def run(rows,p,start,end):
    ef,es,aa,vv=prep(rows,p); trades=[]; nextfree=start; end=min(end,len(rows)-p['max_hold']-3)
    for i in range(max(start,120),end):
        if i<nextfree:continue
        sg=candidate_signal(rows,i,p,ef,es,aa,vv)
        if not sg:continue
        lane,side,anchor=sg; entry=rows[i+2]['o']; a=aa[i]
        raw=abs(entry-(anchor-.05*a if side=='Buy' else anchor+.05*a))
        dist=min(max(raw,entry*p['stop_min_pct']),entry*p['stop_max_pct'])
        sl=entry-dist if side=='Buy' else entry+dist; tp=entry+dist*p['rr'] if side=='Buy' else entry-dist*p['rr']
        # cost expressed in R so entry-quality research stays independent from account size/leverage.
        cost_r=ROUNDTRIP_COST_RATE/(dist/entry)
        exitpx=rows[i+2+p['max_hold']]['c']; reason='TIME'; hold=p['max_hold']
        for k in range(i+2,i+2+p['max_hold']):
            b=rows[k]; hs=b['l']<=sl if side=='Buy' else b['h']>=sl; ht=b['h']>=tp if side=='Buy' else b['l']<=tp
            if hs and ht:exitpx=sl;reason='SL_SAME_BAR';hold=k-(i+1);break
            if hs:exitpx=sl;reason='SL';hold=k-(i+1);break
            if ht:exitpx=tp;reason='TP';hold=k-(i+1);break
        gross_r=((exitpx-entry)/dist)*(1 if side=='Buy' else -1)
        net_r=gross_r-cost_r
        trades.append({'lane':lane,'netR':net_r,'grossR':gross_r,'costR':cost_r,'hold':hold,'reason':reason,'stopPct':dist/entry})
        nextfree=i+2+hold+p['cooldown']
    return trades


def stat(ts):
    n=len(ts); wins=[x['netR'] for x in ts if x['netR']>0]; losses=[x['netR'] for x in ts if x['netR']<0]
    wp=sum(wins); lp=abs(sum(losses)); eq=1.0;peak=1.0;dd=0
    for x in ts:
        eq+=x['netR']*.01;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak*100)
    return {'trades':n,'wins':len(wins),'winRate':len(wins)/n if n else 0,'pf':wp/lp if lp else (99 if wp else 0),
            'expectancyR':sum(x['netR'] for x in ts)/n if n else 0,'netR':sum(x['netR'] for x in ts),
            'avgHoldMin':statistics.mean(x['hold'] for x in ts) if n else 0,'avgCostR':statistics.mean(x['costR'] for x in ts) if n else 0,
            'maxDDPctProxy':dd}


def score(z,min_trades):
    if z['trades']<min_trades:return -10000+z['trades']*20
    s=z['winRate']*220 + min(z['pf'],4)*30 + max(-1,min(1,z['expectancyR']))*45 - z['maxDDPctProxy']*2
    if z['pf']<1:s-=120
    if z['expectancyR']<=0:s-=100
    return s


def mutate(p,g):
    q=deepcopy(p); scale=max(.20,1-g*.03)
    if R.random()<.18:q['family']=R.choice(FAMILIES)
    keys=list(BOUNDS)
    for _ in range(R.randint(4,9)):
        k=R.choice(keys);lo,hi=BOUNDS[k]
        if k in INTS:
            step=max(1,int((hi-lo)*.14*scale));q[k]=int(max(lo,min(hi,q[k]+R.randint(-step,step))))
        else:
            step=(hi-lo)*.16*scale;q[k]=max(lo,min(hi,q[k]+R.uniform(-step,step)))
    if q['ema_fast']>=q['ema_slow']-6:q['ema_fast']=max(8,q['ema_slow']-10)
    if q['stop_min_pct']>q['stop_max_pct']-.001:q['stop_min_pct']=max(.0035,q['stop_max_pct']-.0015)
    return q


def split_idx(n):
    tr=int(n*TRAIN_DAYS/DAYS);va=int(n*(TRAIN_DAYS+VAL_DAYS)/DAYS)
    return tr,va


def qualifies(z,mintr):
    return z['trades']>=mintr and z['winRate']>TARGET_WR and z['pf']>=1.25 and z['expectancyR']>0 and z['maxDDPctProxy']<=10


def capital_feasibility(p,capital=73.0,risk_pct=2.25):
    # Conservative estimate using the median stop width implied by parameter bounds.
    stop_pct=(p['stop_min_pct']+p['stop_max_pct'])/2
    risk_usd=capital*risk_pct/100
    cost_r=ROUNDTRIP_COST_RATE/max(stop_pct,1e-9)
    planned_net=risk_usd*(p['rr']-cost_r)
    return {'capitalUsd':capital,'riskPct':risk_pct,'riskUsd':risk_usd,'assumedStopPct':stop_pct,'estimatedCostR':cost_r,'estimatedTargetNetUsd':planned_net,'meetsOneDollarFloor':planned_net>=1.0}


def main():
    rows=fetch(SYMBOL); n=len(rows);tr_end,val_end=split_idx(n)
    current=deepcopy(BASE); generations=[]; best_val=None;best_params=None;passed=None
    for g in range(1,MAX_GENERATIONS+1):
        candidates=[deepcopy(current)]+[mutate(current,g) for _ in range(CANDIDATES_PER_GEN)]
        ranked=[]
        for p in candidates:
            z=stat(run(rows,p,120,tr_end));ranked.append((score(z,35),p,z))
        ranked.sort(key=lambda x:x[0],reverse=True);_,current,tr=ranked[0]
        va=stat(run(rows,current,tr_end,val_end))
        generations.append({'generation':g,'params':deepcopy(current),'train':tr,'validation':va})
        print('GEN',g,'TRAIN',json.dumps(tr),'VAL',json.dumps(va),'FAMILY',current['family'],flush=True)
        if best_val is None or score(va,MIN_VAL_TRADES)>score(best_val,MIN_VAL_TRADES):best_val=deepcopy(va);best_params=deepcopy(current)
        # Final holdout is touched only after validation itself qualifies.
        if qualifies(va,MIN_VAL_TRADES):
            te=stat(run(rows,current,val_end,n-2))
            print('FINAL_HOLDOUT_CHECK',json.dumps(te),flush=True)
            if qualifies(te,MIN_TEST_TRADES):
                passed={'generation':g,'params':deepcopy(current),'train':tr,'validation':va,'test':te};break
    final_params=passed['params'] if passed else best_params
    final_test=passed['test'] if passed else stat(run(rows,final_params,val_end,n-2)) if final_params else stat([])
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'symbol':SYMBOL,'method':'V54_PER_COIN_TRANSFERABLE_ALPHA_SEARCH',
            'source':'BINANCE_PUBLIC_SPOT_1M_PROXY','days':DAYS,'trainDays':TRAIN_DAYS,'validationDays':VAL_DAYS,'testDays':TEST_DAYS,
            'target':{'winRateGreaterThan':TARGET_WR,'pfMin':1.25,'expectancyRPositive':True,'minValidationTrades':MIN_VAL_TRADES,'minTestTrades':MIN_TEST_TRADES,'maxDDPct':10},
            'passed80OOS':bool(passed),'passed':passed,'bestValidation':best_val,'bestParams':best_params,'finalHoldoutUsingBest':final_test,
            'capitalFeasibilityAt73Usd':capital_feasibility(final_params) if final_params else None,'generations':generations,
            'transferableFeatures':['ATR-normalized trend slope','ATR-normalized pullback depth','volume ratio','liquidity sweep depth','reclaim strength','wick/body rejection','range expansion','two-step confirmation','time-to-target','cost in R'],
            'note':'Research proxy only. 1m spot OHLCV does not include Bybit futures order book, aggressor flow, funding, basis or tick-level slippage. Do not deploy solely from this result.'}
    out=f'v54-{SYMBOL.lower()}-alpha-report.json'
    with open(out,'w') as f:json.dump(report,f,indent=2)
    print('FINAL_REPORT='+json.dumps(report,separators=(',',':')),flush=True)

if __name__=='__main__':main()
