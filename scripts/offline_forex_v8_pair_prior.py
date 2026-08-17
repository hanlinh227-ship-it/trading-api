#!/usr/bin/env python3
import json, os, statistics
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx

# Pair evidence comes from earlier independent F4/F5/F6 meta blocks, not from the May V7 validation.
ROBUST={'AUDCHF','EURAUD','GBPAUD','GBPNZD','GBPUSD','USDCHF','USDJPY'}
WATCH={'CADCHF','EURUSD','USDCAD','AUDJPY'}


def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0: continue
        z=dict(r);z['targetRR']=min(r['rr'],1.5);z['targetR']=z['targetRR'] if r['r']>0 else -1.0
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['targetR']>0 for r in rows);l=sum(r['targetR']<0 for r in rows);n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def quality(r):
    sg=1 if r['side']=='BUY' else -1
    align=(1 if r['h1']==sg else -1)+(0.6 if r['h4']==sg else -0.35)
    q=0.38*r['score']+0.035*r['adx']+0.28*r['impulse']+0.55*r['coh3']+0.22*r['coh24']+0.35*align
    if r['symbol'] in ROBUST:q+=1.25
    elif r['symbol'] in WATCH:q+=0.45
    else:q-=0.35
    if r['side']=='BUY':q+=0.25
    if r['dev']>1.2:q-=0.45
    return q

def select(rows,variant):
    out=[]
    for r in rows:
        if r['adx']<20 or r['impulse']<3:continue
        sg=1 if r['side']=='BUY' else -1
        if r['h1']!=sg:continue
        if variant=='ROBUST_ONLY' and r['symbol'] not in ROBUST:continue
        if variant=='ROBUST_WATCH' and r['symbol'] not in ROBUST|WATCH:continue
        if variant=='ROBUST_H1H4' and (r['symbol'] not in ROBUST or r['h4']!=sg):continue
        if quality(r)<2.4:continue
        out.append(r)
    return out

def main():
    rows=prep(extract_fx());dates=sorted(set(r['date'] for r in rows));devdates=dates[:5];valdates=dates[5:]
    dev=[r for r in rows if r['date'] in devdates];val=[r for r in rows if r['date'] in valdates]
    variants=['ROBUST_ONLY','ROBUST_WATCH','ROBUST_H1H4']
    devstats={v:sm(select(dev,v)) for v in variants}
    # Fixed promotion selection: choose highest dev expectancy among variants with >=15 trades; tie by WR/sample.
    eligible=[v for v in variants if devstats[v].get('n',0)>=15]
    chosen=max(eligible,key=lambda v:(devstats[v]['meanR'],devstats[v]['wr'],devstats[v]['n'])) if eligible else None
    vs=select(val,chosen) if chosen else []
    out={'version':'FOREX V8 INDEPENDENT PAIR-PRIOR','providerCreditsUsed':0,
         'method':'Forex-only F8/V7 continuation. Adds pair prior learned from earlier independent F4-F6 meta evidence, then applies H1/ADX/impulse quality. Variant chosen on May18-22 and frozen for May25-29.',
         'robustPairs':sorted(ROBUST),'watchPairs':sorted(WATCH),'devDates':devdates,'validationDates':valdates,
         'developmentVariants':devstats,'chosenVariant':chosen,'validation':sm(vs),'targetMet':False}
    v=out['validation'];out['targetMet']=bool(v.get('n',0)>=20 and (v.get('wr') or 0)>=80 and 1.0<=(v.get('avgRR') or 0)<=1.5 and v.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v8_pair_prior.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
