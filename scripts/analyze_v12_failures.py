#!/usr/bin/env python3
import json, collections, statistics

with open('data/blind_backtest_v12.json','r',encoding='utf-8') as f:
    d=json.load(f)
key='FRESH_BLIND_2026-08-12_12UTC'
rows=d['samples'][key]['tests']
usable=[r for r in rows if r.get('decision') and r.get('outcome',{}).get('result') in ('TP','SL')]

def stat(rs):
    if not rs:return {'n':0}
    w=sum(r['outcome']['result']=='TP' for r in rs)
    avg_rr=sum(r['plannedRR'] for r in rs)/len(rs)
    exp=sum((r['plannedRR'] if r['outcome']['result']=='TP' else -1) for r in rs)/len(rs)
    return {'n':len(rs),'wins':w,'losses':len(rs)-w,'winRate':round(100*w/len(rs),2),'avgRR':round(avg_rr,3),'expectancyR':round(exp,3)}

out={'overall':stat(usable)}
for field,fn in {
    'regime':lambda r:r['model']['regime'],
    'profile':lambda r:r['model']['profile'],
    'side':lambda r:r['decision'],
    'scoreBucket':lambda r:'0-2' if abs(r['score'])<2 else '2-4' if abs(r['score'])<4 else '4-7' if abs(r['score'])<7 else '7+',
    'chaseBucket':lambda r:'high' if abs(r['model'].get('chaseAdjustment',0))>=1.2 else 'low',
    'htfLtfAgreement':lambda r:'agree' if (r['model'].get('htfScore',0)>=0)==(r['model'].get('ltfScore',0)>=0) else 'conflict',
    'scoreHTFAgreement':lambda r:'agree' if (r['score']>=0)==(r['model'].get('htfScore',0)>=0) else 'conflict',
    'scoreLTFAgreement':lambda r:'agree' if (r['score']>=0)==(r['model'].get('ltfScore',0)>=0) else 'conflict',
}.items():
    groups=collections.defaultdict(list)
    for r in usable:groups[fn(r)].append(r)
    out[field]={str(k):stat(v) for k,v in sorted(groups.items(),key=lambda x:str(x[0]))}

# rank simple observable features by winner vs loser averages to guide next version without peeking at any new sample
features=['score']
for name,getter in {
    'absScore':lambda r:abs(r['score']),
    'htfScore':lambda r:r['model'].get('htfScore',0),
    'absHtf':lambda r:abs(r['model'].get('htfScore',0)),
    'ltfScore':lambda r:r['model'].get('ltfScore',0),
    'absLtf':lambda r:abs(r['model'].get('ltfScore',0)),
    'chaseAbs':lambda r:abs(r['model'].get('chaseAdjustment',0)),
    'rs':lambda r:r['model'].get('relativeStrengthScore',0),
    'rangePos':lambda r:r['model'].get('rangePositionH1',.5),
    'm15Vol':lambda r:r.get('snapshot',{}).get('M15',{}).get('volumeRatio',0) if 'snapshot' in r else 0,
    'm15Dist':lambda r:abs(r.get('snapshot',{}).get('M15',{}).get('dist20ATR',0)) if 'snapshot' in r else 0,
}.items():
    ws=[getter(r) for r in usable if r['outcome']['result']=='TP']
    ls=[getter(r) for r in usable if r['outcome']['result']=='SL']
    if ws and ls:out.setdefault('featureMeans',{})[name]={'TP':round(statistics.mean(ws),4),'SL':round(statistics.mean(ls),4)}

# list losers and winners compactly for pattern inspection
out['trades']=[{
    'symbol':r['symbol'],'side':r['decision'],'result':r['outcome']['result'],'score':r['score'],'rr':r['plannedRR'],
    'profile':r['model']['profile'],'regime':r['model']['regime'],'htf':round(r['model'].get('htfScore',0),2),'ltf':round(r['model'].get('ltfScore',0),2),
    'chase':round(r['model'].get('chaseAdjustment',0),2),'rs':round(r['model'].get('relativeStrengthScore',0),2),
    'pos':round(r['model'].get('rangePositionH1',.5),2)
} for r in usable]
with open('data/v12_diagnostics.json','w') as f:json.dump(out,f,indent=2)
print(json.dumps({k:v for k,v in out.items() if k not in ('trades',)},indent=2))