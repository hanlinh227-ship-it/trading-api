#!/usr/bin/env python3
import json, os, sys, itertools
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import blind_backtest_crypto as v6
import v14_dev_search as v14

DEV=[('DEV_12AUG','2026-08-12T12:00:00Z'),('DEV_05AUG','2026-08-05T12:00:00Z')]
LOOKBACK=48;STOP_FACTOR=.75;HOURS=96
HIGH_RRS=[1.7,1.9,2.1]
THRESHOLDS=[2.5,3.5,5.0,6.5]
MODES=['confidence','trend_or_confidence','trend_only']

def rr_for(row,mode,thr,high):
    mom=abs(row['feat']['momScore']);rg=row['model']['regime']
    if mode=='confidence':strong=mom>=thr
    elif mode=='trend_only':strong=rg=='trend'
    else:strong=rg=='trend' or mom>=thr
    return high if strong else 1.5

def eval_cfg(rows,breadth,mode,thr,high):
    w=l=u=0;rrsum=0;resolved_rr=[]
    for r in rows:
        side=v14.choose_side('tsmom_structure',r,breadth);en=r['en'];a=r['su']['M15']['atr14'] or en*.01;base=v6.profile(r['sym'])['stopBase'];recent=r['fr']['M15'][-LOOKBACK:];floor=STOP_FACTOR*base*a;rr=rr_for(r,mode,thr,high)
        if side=='BUY':struct=min(x['low'] for x in recent);risk=max(floor,en-struct);sl=en-risk;tp=en+rr*risk
        else:struct=max(x['high'] for x in recent);risk=max(floor,struct-en);sl=en+risk;tp=en-rr*risk
        z=v14.outcome(side,en,sl,tp,r['future'])
        if z=='TP':w+=1;rrsum+=rr;resolved_rr.append(rr)
        elif z=='SL':l+=1;rrsum-=1;resolved_rr.append(rr)
        else:u+=1
    n=w+l
    return {'wins':w,'losses':l,'unresolved':u,'winRate':round(100*w/n,2) if n else None,'avgRR':round(sum(resolved_rr)/n,3) if n else None,'expectancyR':round(rrsum/n,3) if n else None}

def main():
    ds={}
    for name,cut in DEV:
        rows,b=v14.load(cut);ds[name]={'rows':rows,'breadth':b}
    grid=[]
    for mode,thr,high in itertools.product(MODES,THRESHOLDS,HIGH_RRS):
        if mode=='trend_only' and thr!=THRESHOLDS[0]:continue
        per={k:eval_cfg(v['rows'],v['breadth'],mode,thr,high) for k,v in ds.items()};minwr=min(x['winRate'] for x in per.values());minexp=min(x['expectancyR'] for x in per.values());avgrr=sum(x['avgRR'] for x in per.values())/2;avgwr=sum(x['winRate'] for x in per.values())/2;avgexp=sum(x['expectancyR'] for x in per.values())/2
        robust=minwr+12*minexp+4*(avgrr-1.5)+.1*avgwr+3*avgexp
        grid.append({'mode':mode,'threshold':thr,'highRR':high,'perSample':per,'minWinRate':round(minwr,2),'minExpectancyR':round(minexp,3),'avgRR':round(avgrr,3),'avgWinRate':round(avgwr,2),'avgExpectancyR':round(avgexp,3),'robustScore':round(robust,3)})
    feasible=[x for x in grid if x['minExpectancyR']>0 and x['minWinRate']>=40 and x['avgRR']>1.5]
    top=sorted(feasible,key=lambda x:(x['robustScore'],x['avgRR'],x['minWinRate']),reverse=True)[:20]
    with open('data/v14_rr_search.json','w') as f:json.dump({'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'V14 dynamic RR development only; tsmom_structure locked; 48 M15 stop; .75 profile ATR floor; base RR1.5; higher RR only by pre-cutoff confidence/regime','top':top,'grid':grid},f,indent=2)
    print(json.dumps({'top':top[:10]},indent=2))
if __name__=='__main__':main()
