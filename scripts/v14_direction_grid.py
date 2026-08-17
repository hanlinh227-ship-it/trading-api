#!/usr/bin/env python3
import json, math
from itertools import product
from datetime import datetime, timezone

SRC='data/v13_direction_diagnostic.json'
WV=[0.4,0.7,1.0,1.3]
W4=[0.5,1.0,1.5,2.0]
WM=[0.5,1.0,1.5]
W12=[0.0,0.4,0.8]
WB=[0.0,0.5,1.0]
WR=[0.0,0.5,1.0]
RR=1.5

def clamp(x,a=-1,b=1):return max(a,min(b,x))
def side_sign(side):return 1 if side=='BUY' else -1
def calc(t,b4,b12,w):
    wv,w4,wm,w12,wb,wr=w
    v=side_sign(t['side'])*clamp(abs(t['score'])/5,0.2,1)
    m4=clamp(t['h1ret4']/0.012)
    mm=clamp(t['m15ret4']/0.006)
    m12=clamp(t['h1ret12']/0.025)
    breadth=clamp((b4-.5)/.25)
    # Broad acceleration/reversal: difference between very recent and 12h participation.
    accel=clamp((b4-b12)/.35)
    pos=1-2*t['rangePos']  # positive near lows, negative near highs
    rg=t['regime']
    # Time-series momentum gets more say in transition, range location gets more say in range.
    k4=1.25 if rg=='transition' else 1.0
    kr=1.5 if rg=='range' else .35
    sc=wv*v+w4*k4*m4+wm*mm+w12*m12+wb*(.55*breadth+.45*accel)+wr*kr*pos
    # New/high-beta coins were unstable under HTF scoring; rely less on V6 direction.
    if t['profile'] in ('new_high_beta','alt'):
        sc-=0.45*wv*v
        sc+=0.35*w4*k4*m4+0.25*wm*mm
    return 1 if sc>=0 else -1

def result_for(t,s):
    return t['result'] if s==side_sign(t['side']) else t['opposite']
def evaluate(sample,w):
    b4=sample['breadth4h'];b12=sample['breadth12h'];win=loss=unr=0
    for t in sample['trades']:
        r=result_for(t,calc(t,b4,b12,w))
        if r=='TP':win+=1
        elif r=='SL':loss+=1
        else:unr+=1
    n=win+loss;wr=100*win/n if n else 0;exp=(win*RR-loss)/n if n else -9
    return {'wins':win,'losses':loss,'unresolved':unr,'winRate':round(wr,2),'expectancyR':round(exp,3)}
def main():
    p=json.load(open(SRC));grid=[]
    for w in product(WV,W4,WM,W12,WB,WR):
        per={k:evaluate(s,w) for k,s in p['samples'].items()};wins=[x['winRate'] for x in per.values()];exps=[x['expectancyR'] for x in per.values()]
        grid.append({'weights':{'v6':w[0],'h1_4':w[1],'m15':w[2],'h1_12':w[3],'breadth':w[4],'range':w[5]},'minWin':min(wins),'avgWin':round(sum(wins)/len(wins),2),'minExp':min(exps),'avgExp':round(sum(exps)/len(exps),3),'samples':per})
    top=sorted(grid,key=lambda x:(x['minWin'],x['minExp'],x['avgWin']),reverse=True)[:30]
    out={'generatedAt':datetime.now(timezone.utc).isoformat(),'source':SRC,'rrAssumption':RR,'topRobust':top}
    json.dump(out,open('data/v14_direction_grid.json','w'),indent=2)
    print(json.dumps(top[:10],indent=2))
if __name__=='__main__':main()
