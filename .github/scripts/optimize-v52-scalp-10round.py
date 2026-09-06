#!/usr/bin/env python3
import json, math, random, statistics, time, urllib.parse, urllib.request
from copy import deepcopy
from datetime import datetime, timezone

SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT']
DAYS=10
TRAIN_DAYS=7
VAL_DAYS=3
START_EQUITY=73.0
ROUNDTRIP_COST_RATE=0.00130
MIN_PLANNED_NET_USD=1.0
RNG=random.Random(5102026)

BASE={
 'ema_fast':20,'ema_slow':50,'atr_n':14,'vol_n':20,
 'trend_slope_bars':5,'trend_slope_atr':0.10,
 'pullback_atr':0.18,'reaccel_body_atr':0.10,'reaccel_vol':1.10,
 'sweep_lookback':24,'sweep_reclaim_atr':0.05,'sweep_vol':1.25,
 'breakout_enabled':False,'breakout_lookback':24,'breakout_vol':1.40,'retest_atr':0.12,
 'rr_trend':0.95,'rr_sweep':0.90,'rr_breakout':0.90,
 'stop_min_pct':0.0011,'stop_max_pct':0.0035,'max_hold':5,
 'cooldown':2,'risk_pct':2.0,'body_filter_atr':0.08
}

BOUNDS={
 'ema_fast':(8,30),'ema_slow':(32,100),'trend_slope_bars':(3,12),'trend_slope_atr':(0.04,0.35),
 'pullback_atr':(0.05,0.35),'reaccel_body_atr':(0.04,0.30),'reaccel_vol':(0.8,2.2),
 'sweep_lookback':(12,60),'sweep_reclaim_atr':(0.0,0.20),'sweep_vol':(0.8,2.5),
 'breakout_lookback':(12,60),'breakout_vol':(0.9,2.8),'retest_atr':(0.04,0.30),
 'rr_trend':(0.65,1.35),'rr_sweep':(0.60,1.30),'rr_breakout':(0.65,1.30),
 'stop_min_pct':(0.0008,0.0025),'stop_max_pct':(0.0020,0.0060),'max_hold':(2,7),'cooldown':(1,8),
 'risk_pct':(1.0,2.25),'body_filter_atr':(0.03,0.25)
}
INTS={'ema_fast','ema_slow','trend_slope_bars','sweep_lookback','breakout_lookback','max_hold','cooldown'}


def get_json(url,retries=5):
    for i in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'trading-api-v52-optimizer'})
            with urllib.request.urlopen(req,timeout=25) as r:return json.loads(r.read().decode())
        except Exception:
            if i==retries-1:raise
            time.sleep(1+i)


def fetch(symbol):
    end=int(time.time()*1000); start=end-DAYS*86400000; out=[]; cur=start
    while cur<end:
        q=urllib.parse.urlencode({'symbol':symbol,'interval':'1m','startTime':cur,'endTime':end,'limit':1000})
        rows=get_json('https://data-api.binance.vision/api/v3/klines?'+q)
        if not rows:break
        for x in rows:out.append({'t':int(x[0]),'o':float(x[1]),'h':float(x[2]),'l':float(x[3]),'c':float(x[4]),'v':float(x[5])})
        nxt=int(rows[-1][0])+60000
        if nxt<=cur:break
        cur=nxt
        if len(rows)<1000:break
        time.sleep(.03)
    d={r['t']:r for r in out}
    return [d[k] for k in sorted(d)]


def ema(vals,n):
    a=2/(n+1); out=[]; e=None
    for x in vals:
        e=x if e is None else a*x+(1-a)*e; out.append(e)
    return out


def atr(rows,n):
    tr=[]
    for i,r in enumerate(rows):
        pc=rows[i-1]['c'] if i else r['c']; tr.append(max(r['h']-r['l'],abs(r['h']-pc),abs(r['l']-pc)))
    return ema(tr,n)


def rollmean(vals,n):
    out=[None]*len(vals); s=0
    for i,x in enumerate(vals):
        s+=x
        if i>=n:s-=vals[i-n]
        if i>=n-1:out[i]=s/n
    return out


def extreme(rows,i,n,side):
    if i<n:return None
    xs=rows[i-n:i]
    return max(x['h'] for x in xs) if side=='high' else min(x['l'] for x in xs)


def prepared(rows,p):
    c=[x['c'] for x in rows]; v=[x['v'] for x in rows]
    return ema(c,p['ema_fast']),ema(c,p['ema_slow']),atr(rows,p['atr_n']),rollmean(v,p['vol_n'])


def signal(rows,i,p,ef,es,aa,vv):
    if i<max(110,p['ema_slow']+15,p['sweep_lookback']+5) or not vv[i] or aa[i]<=0:return None
    r=rows[i]; prev=rows[i-1]; a=aa[i]; volr=r['v']/max(vv[i],1e-12); body=abs(r['c']-r['o'])/a
    if body<p['body_filter_atr']:return None
    hi=extreme(rows,i,p['sweep_lookback'],'high'); lo=extreme(rows,i,p['sweep_lookback'],'low')
    if lo and r['l']<lo and r['c']>lo+p['sweep_reclaim_atr']*a and r['c']>r['o'] and r['c']>prev['c'] and volr>=p['sweep_vol']:
        return ('SWEEP_RECLAIM','Buy',p['rr_sweep'])
    if hi and r['h']>hi and r['c']<hi-p['sweep_reclaim_atr']*a and r['c']<r['o'] and r['c']<prev['c'] and volr>=p['sweep_vol']:
        return ('SWEEP_RECLAIM','Sell',p['rr_sweep'])
    sb=p['trend_slope_bars']
    if i>sb:
        up=ef[i]>es[i] and (ef[i]-ef[i-sb])/a>=p['trend_slope_atr']
        dn=ef[i]<es[i] and (ef[i-sb]-ef[i])/a>=p['trend_slope_atr']
        recent=rows[i-3:i]
        if up:
            touched=any(x['l']<=ef[i]+p['pullback_atr']*a for x in recent)
            if touched and r['c']>prev['h'] and r['c']>ef[i] and r['c']>r['o'] and (r['c']-r['o'])/a>=p['reaccel_body_atr'] and volr>=p['reaccel_vol']:
                return ('TREND_REACCEL','Buy',p['rr_trend'])
        if dn:
            touched=any(x['h']>=ef[i]-p['pullback_atr']*a for x in recent)
            if touched and r['c']<prev['l'] and r['c']<ef[i] and r['c']<r['o'] and (r['o']-r['c'])/a>=p['reaccel_body_atr'] and volr>=p['reaccel_vol']:
                return ('TREND_REACCEL','Sell',p['rr_trend'])
    if p['breakout_enabled']:
        lb=p['breakout_lookback']
        for j in range(max(lb+2,i-4),i):
            jhi=extreme(rows,j,lb,'high'); jlo=extreme(rows,j,lb,'low')
            if not jhi or not vv[j]:continue
            jvr=rows[j]['v']/max(vv[j],1e-12)
            if rows[j]['c']>jhi and jvr>=p['breakout_vol'] and ef[i]>es[i]:
                if r['l']<=jhi+p['retest_atr']*a and r['c']>jhi and r['c']>prev['c'] and r['c']>r['o'] and volr>=p['reaccel_vol']:
                    return ('BREAKOUT_RETEST','Buy',p['rr_breakout'])
            if rows[j]['c']<jlo and jvr>=p['breakout_vol'] and ef[i]<es[i]:
                if r['h']>=jlo-p['retest_atr']*a and r['c']<jlo and r['c']<prev['c'] and r['c']<r['o'] and volr>=p['reaccel_vol']:
                    return ('BREAKOUT_RETEST','Sell',p['rr_breakout'])
    return None


def sltp(rows,i,lane,side,entry,rr,a,p):
    if lane=='SWEEP_RECLAIM': anchor=rows[i]['l'] if side=='Buy' else rows[i]['h']
    elif lane=='BREAKOUT_RETEST': anchor=rows[i]['l'] if side=='Buy' else rows[i]['h']
    else:
        xs=rows[max(0,i-2):i+1]; anchor=min(x['l'] for x in xs) if side=='Buy' else max(x['h'] for x in xs)
    raw=abs(entry-(anchor-.05*a if side=='Buy' else anchor+.05*a))
    dist=min(max(raw,entry*p['stop_min_pct']),entry*p['stop_max_pct'])
    sl=entry-dist if side=='Buy' else entry+dist; tp=entry+dist*rr if side=='Buy' else entry-dist*rr
    return sl,tp,dist


def run(rows,p,start_i,end_i):
    ef,es,aa,vv=prepared(rows,p); eq=START_EQUITY; peak=eq; maxdd=0; trades=[]; next_free=start_i
    end_i=min(end_i,len(rows)-p['max_hold']-2)
    for i in range(max(start_i,110),end_i):
        if i<next_free:continue
        sg=signal(rows,i,p,ef,es,aa,vv)
        if not sg:continue
        lane,side,rr=sg; entry=rows[i+1]['o']; sl,tp,dist=sltp(rows,i,lane,side,entry,rr,aa[i],p)
        risk=eq*p['risk_pct']/100; qty=risk/dist; cost=qty*entry*ROUNDTRIP_COST_RATE; planned=risk*rr-cost
        if planned<MIN_PLANNED_NET_USD:continue
        exitpx=rows[i+p['max_hold']+1]['c']; reason='TIME'; hold=p['max_hold']
        for k in range(i+1,i+p['max_hold']+1):
            b=rows[k]
            hs=b['l']<=sl if side=='Buy' else b['h']>=sl; ht=b['h']>=tp if side=='Buy' else b['l']<=tp
            if hs and ht: exitpx=sl;reason='SL_SAME_BAR';hold=k-i;break
            if hs: exitpx=sl;reason='SL';hold=k-i;break
            if ht: exitpx=tp;reason='TP';hold=k-i;break
        gross=(exitpx-entry)*qty*(1 if side=='Buy' else -1); net=gross-cost; eq=max(.01,eq+net);peak=max(peak,eq);maxdd=max(maxdd,(peak-eq)/peak*100)
        trades.append({'lane':lane,'net':net,'hold':hold,'reason':reason})
        next_free=i+hold+p['cooldown']
    return trades,eq,maxdd


def stat(ts):
    n=len(ts); wins=[x['net'] for x in ts if x['net']>0]; losses=[x['net'] for x in ts if x['net']<0]
    win=sum(wins); loss=abs(sum(losses))
    return {'trades':n,'winRate':len(wins)/n if n else 0,'pf':win/loss if loss else (99 if win else 0),'expectancy':sum(x['net'] for x in ts)/n if n else 0,'net':sum(x['net'] for x in ts),'avgHold':statistics.mean(x['hold'] for x in ts) if n else 0}


def eval_params(data,p,split):
    alltr=[]; worstdd=0
    for s,rows in data.items():
        cut=int(len(rows)*TRAIN_DAYS/DAYS)
        a,b=(110,cut) if split=='train' else (cut,len(rows)-2)
        ts,eq,dd=run(rows,p,a,b); alltr+=ts; worstdd=max(worstdd,dd)
    z=stat(alltr);z['maxDD']=worstdd;return z


def score(z):
    if z['trades']<25:return -1000+z['trades']
    s=z['winRate']*120 + min(z['pf'],3)*18 + max(-2,min(2,z['expectancy']))*12 - z['maxDD']*1.2
    if z['pf']<1:s-=50
    if z['expectancy']<=0:s-=40
    return s


def mutate(p,roundn):
    q=deepcopy(p); scale=max(.18,1.0-roundn*.075)
    keys=[k for k in BOUNDS if k not in ('atr_n','vol_n')]
    for _ in range(RNG.randint(3,7)):
        k=RNG.choice(keys); lo,hi=BOUNDS[k]; cur=q[k]
        if k in INTS:
            step=max(1,int((hi-lo)*.15*scale)); q[k]=int(max(lo,min(hi,cur+RNG.randint(-step,step))))
        else:
            step=(hi-lo)*.16*scale; q[k]=max(lo,min(hi,cur+RNG.uniform(-step,step)))
    if RNG.random()<.12:q['breakout_enabled']=not q['breakout_enabled']
    if q['ema_fast']>=q['ema_slow']-5:q['ema_fast']=max(8,q['ema_slow']-8)
    return q


def main():
    data={s:fetch(s) for s in SYMBOLS}; current=deepcopy(BASE); rounds=[]; best_val=None; best_p=None
    for r in range(1,11):
        candidates=[deepcopy(current)]+[mutate(current,r) for _ in range(70)]
        ranked=[]
        for p in candidates:
            tr=eval_params(data,p,'train'); ranked.append((score(tr),p,tr))
        ranked.sort(key=lambda x:x[0],reverse=True); _,current,train=ranked[0]
        val=eval_params(data,current,'val')
        row={'round':r,'params':current,'train':train,'validation':val};rounds.append(row)
        print('ROUND',r,'TRAIN',json.dumps(train),'VAL',json.dumps(val),'PARAMS',json.dumps(current,separators=(',',':')))
        if best_val is None or score(val)>score(best_val):best_val=val;best_p=deepcopy(current)
        if val['trades']>=25 and val['winRate']>=.80 and val['pf']>=1.20 and val['expectancy']>0 and val['maxDD']<=12:
            print('STOP_CRITERIA_REACHED',r);break
    report={'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'10_ROUND_WALK_FORWARD_PRECISION_SCALP','source':'BINANCE_PUBLIC_SPOT_1M_PROXY','symbols':SYMBOLS,'days':DAYS,'trainDays':TRAIN_DAYS,'validationDays':VAL_DAYS,'costRate':ROUNDTRIP_COST_RATE,'minPlannedNetUsd':MIN_PLANNED_NET_USD,'rounds':rounds,'bestValidation':best_val,'bestParams':best_p,'stopCriteria':{'minTrades':25,'winRate':.80,'pf':1.20,'expectancyPositive':True,'maxDDPct':12},'fullFidelityMicrostructure':False}
    with open('v52-10round-optimizer-report.json','w') as f:json.dump(report,f,indent=2)
    print('FINAL_REPORT='+json.dumps(report,separators=(',',':')))

if __name__=='__main__':main()
