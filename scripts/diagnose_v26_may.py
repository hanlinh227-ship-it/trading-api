#!/usr/bin/env python3
import json, statistics
from collections import defaultdict

PATH='data/blind_backtest_v26.json'


def summary(rows):
    resolved=[r for r in rows if r.get('outcome',{}).get('result') in ('TP','SL')]
    wins=[r for r in resolved if r['outcome']['result']=='TP']
    losses=[r for r in resolved if r['outcome']['result']=='SL']
    total=sum(r['plannedRR'] if r['outcome']['result']=='TP' else -1 for r in resolved)
    def med(vals):
        vals=[v for v in vals if isinstance(v,(int,float))]
        return round(statistics.median(vals),3) if vals else None
    return {
        'trades':len(rows),'resolved':len(resolved),'wins':len(wins),'losses':len(losses),
        'unresolved':len(rows)-len(resolved),
        'wr':round(100*len(wins)/len(resolved),2) if resolved else None,
        'expectancyR':round(total/len(resolved),3) if resolved else None,
        'medianRiskPct':med([100*r['risk']/r['entry'] for r in resolved if r.get('entry')]),
        'medianOutcomeCandles':med([r.get('outcome',{}).get('candles') for r in resolved]),
        'medianSLCandles':med([r.get('outcome',{}).get('candles') for r in losses]),
        'medianTPCandles':med([r.get('outcome',{}).get('candles') for r in wins]),
    }


def grouped(rows,key):
    d=defaultdict(list)
    for r in rows:d[key(r)].append(r)
    return {str(k):summary(v) for k,v in sorted(d.items(),key=lambda kv:str(kv[0]))}


def breadth_bucket(r):
    x=r.get('priceBreadth',.5)
    if x<=.10:return 'extreme_bear_<=0.10'
    if x<.30:return 'bear_0.10_0.30'
    if x<.70:return 'middle_0.30_0.70'
    if x<.90:return 'bull_0.70_0.90'
    return 'extreme_bull_>=0.90'


def flow_state(r):
    f=r.get('flow') or {}
    if not f.get('available'):return 'unavailable'
    return 'aligned' if r.get('flowAligned') else 'conflict_or_neutral'


def side(r): return r.get('decision','NONE')

def main():
    with open(PATH) as f:p=json.load(f)
    rows=[r for s in p['samples'].values() for r in s['tests']]
    out={
        'overall':summary(rows),
        'byDate':{k:summary(v['tests'])|{
            'priceBreadth':v['priceBreadth'],'flowBreadth':v['flowBreadth'],
            'flowMedian':v['flowMedian'],'flowCoverage':v['flowCoverage'],'marketRegime':v['marketRegime']
        } for k,v in p['samples'].items()},
        'byBreadthBucket':grouped(rows,breadth_bucket),
        'byFlowState':grouped(rows,flow_state),
        'byProfile':grouped(rows,lambda r:(r.get('model') or {}).get('profile','unknown')),
        'byInternalRegime':grouped(rows,lambda r:(r.get('model') or {}).get('regime','unknown')),
        'byMarketRegime':grouped(rows,lambda r:r.get('marketRegime','unknown')),
        'bySide':grouped(rows,side),
    }
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
